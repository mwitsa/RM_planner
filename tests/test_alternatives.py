"""Regression checks for rolling proposals and unchanged imported demand."""
import unittest
from copy import deepcopy
from dataclasses import replace
from tempfile import TemporaryDirectory
from pathlib import Path

from rm_planner.planning.alternatives import build_context, evaluate, compare, baseline_rows, signature
from rm_planner.planning.proposal_store import load_preferences, save_preferences, save_approval
from rm_planner.inventory.wonton_weight_store import WontonWeightSettings
from test_plan_engine import order, stock, class_definition, balanced_capacity, RANGES


class AlternativeTests(unittest.TestCase):
    def context(self, **settings):
        a = order('a', day='30', month='09')
        a = replace(a, prod_date='14', prod_month='09', prod_year='2026', order_no='A')
        b = replace(a, record_id='b', order_no='B', prod_date='18')
        profiles = {j: dict(egg='มีไข่', soup_rank=0, status='ready', earliest='2026-09-14',
                           date='2026-09-14', max_qty=1000, reviewer='staff') for j in ('a', 'b')}
        return build_context([a,b], [stock((('51-55',100),), market_type='domestic')], RANGES,
            balanced_capacity(3000,3000), [class_definition('Country','AUS','2')],
            WontonWeightSettings(10,10), '2026-09-14', dict(freeze_cost=10,stop_cost=100,freeze_percent=100,**settings), profiles)

    def test_pull_from_day_five_conserves_demand_and_stock(self):
        c = self.context()
        before = deepcopy(c)
        plans = compare(c)
        p = plans[2]
        self.assertEqual(c, before)
        self.assertLess(p['remaining'], plans[0]['remaining'])
        self.assertEqual(p['remaining'], 80)
        for j in c['jobs']:
            self.assertAlmostEqual(sum(r['qty'] for r in p['rows'] if r['job']==j['id']), j['qty'])
        self.assertEqual(p['daily'][-1]['remaining'], plans[0]['daily'][-1]['remaining'])

    def test_locked_cannot_move(self):
        c = self.context()
        c['jobs'][1]['locked'] = True
        self.assertEqual(compare(c)[2]['moved'], 0)
        rows = baseline_rows(c)
        rows[1]['day'] = c['start']
        self.assertTrue(evaluate(c,rows)['errors'])

    def test_factory_holidays_cannot_be_scheduled(self):
        c = {
            'start': '2026-09-15',  # Tuesday
            'settings': {'lookahead': 1, 'adjust_from': '2026-09-15', 'shift_hours': 8,
                         'setup_minutes': 0, 'freeze_percent': None, 'freeze_cost': None,
                         'stop_cost': None},
            'jobs': [
                {'id': 'holiday-job', 'order': 'HOLIDAY', 'qty': 100, 'day': '2026-09-15',
                 'locked': False, 'earliest': '', 'status': 'unknown', 'ready_date': '',
                 'reviewer': '', 'max_qty': 0, 'line': 'RAW', 'market': 'domestic',
                 'egg': '', 'soup_rank': None, 'sku': 'SKU', 'cups': 10,
                 'yield_rate': 10, 'stock_size': 'M', 'size': 'M', 'due': '2026-09-15'},
            ],
            'lots': [], 'capacity': {'RAW': 1000, 'COOKED': 1000}, 'forecasts': [],
        }
        rows = [{'job': 'holiday-job', 'day': '2026-09-15', 'qty': 100}]

        result = evaluate(c, rows)

        self.assertTrue(any('หยุดผลิตวันจันทร์และวันอังคาร' in error for error in result['errors']))
        self.assertFalse(any(item['day'] == '2026-09-15' for item in result['schedule']))

    def test_partial_readiness_caps_total_pulled_quantity(self):
        c = self.context()
        c['jobs'][1].update(status='partial', max_qty=300)
        p = compare(c)[2]
        self.assertAlmostEqual(sum(r['qty'] for r in p['rows'] if r['job']=='b' and r['day']==c['start']),300)

    def test_unknown_material_is_conditional_not_ready(self):
        c = self.context()
        c['jobs'][1]['status'] = 'unknown'
        self.assertEqual(compare(c)[2]['status'], 'conditional')
        self.assertEqual(compare(c)[1]['moved'], 0)

    def test_unknown_costs_remain_none_and_no_cost_ranking(self):
        c = self.context()
        c['settings']['freeze_cost'] = None
        plans = compare(c)
        self.assertIsNone(plans[0]['cost'])
        self.assertEqual(plans[3]['moved'], 0)

    def test_no_borrowing_future_arrival(self):
        c = self.context()
        c['lots'][0]['day'] = '2026-09-18'
        self.assertTrue(compare(c)[0]['errors'])

    def test_s_and_ss_share_one_stock_pool(self):
        c = self.context()
        c['lots'][0]['size'] = 'S+'
        for j, size in zip(c['jobs'], ('S','SS')):
            j.update(size=size, stock_size='S+')
        p = compare(c)[2]
        self.assertEqual(p['remaining'],80)
        self.assertEqual({j['size'] for j in c['jobs']},{'S','SS'})

    def test_capacity_and_setup_time(self):
        c = self.context()
        c['jobs'][1]['sku']='another'
        c['capacity']['COOKED']=1500
        p = compare(c)[2]
        self.assertLessEqual(p['daily'][0]['hours']['COOKED'],8.000001)
        self.assertLess(sum(r['qty'] for r in p['rows'] if r['day']==c['start']),1500)

    def test_raw_orders_with_the_same_code_share_one_run(self):
        first = order('raw-a', group_2='Raw Wonton', group_1='Raw item A', order_cups=100)
        second = order('raw-b', group_2='Raw Wonton', group_1='Raw item B', order_cups=100)
        first = replace(first, prod_date='17', prod_month='09', prod_year='2026', order_no='RAW-A')
        second = replace(second, prod_date='17', prod_month='09', prod_year='2026', order_no='RAW-B')
        first.code = second.code = 'SAME-RAW-CODE'
        profiles = {
            item.record_id: dict(egg='มีไข่', soup_rank=0, status='ready', earliest='2026-09-17',
                                 date='2026-09-17', max_qty=1000, reviewer='staff')
            for item in (first, second)
        }
        context = build_context(
            [first, second],
            [],
            RANGES,
            balanced_capacity(2_000, 2_000),
            [class_definition('Country', 'AUS', '2')],
            WontonWeightSettings(10, 10),
            '2026-09-17',
            dict(freeze_cost=10, stop_cost=100, freeze_percent=100),
            profiles,
        )

        plan = compare(context)[0]
        raw_schedule = [entry for entry in plan['schedule'] if entry['line'] == 'RAW']

        self.assertEqual(plan['changes'], 0)
        self.assertEqual(len(raw_schedule), 2)
        self.assertAlmostEqual(raw_schedule[1]['start_hours'], 0.4)

        # RAW products with different CODEs still run continuously: unlike
        # cooked work, a raw change must not insert the 30-minute break.
        context['jobs'][1]['code'] = 'DIFFERENT-RAW-CODE'
        plan = compare(context)[0]
        raw_schedule = [entry for entry in plan['schedule'] if entry['line'] == 'RAW']
        self.assertEqual(plan['changes'], 0)
        self.assertAlmostEqual(raw_schedule[1]['start_hours'], 0.4)

    def test_workflow_rules_order_only_proposed_cooked_plans(self):
        base_job = dict(order='test', code='', qty=100, day='2026-09-16', locked=False,
                        earliest='', status='unknown', ready_date='', reviewer='', max_qty=0,
                        line='COOKED', market='domestic', egg='มีไข่', soup_rank=0,
                        cups=10, yield_rate=10, stock_size='M', size='M', due='2026-09-16')
        context = {
            'start': '2026-09-16',
            'settings': {'lookahead': 1, 'adjust_from': '2026-09-16', 'shift_hours': 8,
                         'setup_minutes': 0, 'freeze_percent': None, 'freeze_cost': None,
                         'stop_cost': None},
            'jobs': [
                dict(base_job, id='a', sku='A', class_groups={'country': 'd'}),
                dict(base_job, id='b', sku='B', class_groups={'country': 'e'}),
            ],
            'lots': [], 'capacity': {'RAW': 1000, 'COOKED': 1000}, 'forecasts': [],
            'operation_rules': (
                {'name': 'Country order', 'nodes': (
                    {'class': 'Country', 'group': 'E'}, {'class': 'Country', 'group': 'D'},
                )},
            ),
        }

        plans = compare(context)
        baseline = [entry['job'] for entry in plans[0]['schedule'] if entry['line'] == 'COOKED']
        proposed = [entry['job'] for entry in plans[1]['schedule'] if entry['line'] == 'COOKED']

        self.assertEqual(baseline, ['a', 'b'])
        self.assertEqual(proposed, ['b', 'a'])

        # Workflow rules are deliberately a cooked-wonton sequencing tool;
        # RAW keeps its normal production order even when the same classes match.
        raw_context = dict(context, jobs=[dict(job, line='RAW') for job in context['jobs']])
        raw_plan = evaluate(raw_context, baseline_rows(raw_context), apply_operation_rules=True)
        raw_order = [entry['job'] for entry in raw_plan['schedule'] if entry['line'] == 'RAW']
        self.assertEqual(raw_order, ['a', 'b'])

    def test_schedule_marks_the_uncovered_rm_share(self):
        context = {
            'start': '2026-09-16',
            'settings': {'lookahead': 1, 'adjust_from': '2026-09-16', 'shift_hours': 8,
                         'setup_minutes': 0, 'freeze_percent': None, 'freeze_cost': None,
                         'stop_cost': None},
            'jobs': [
                dict(id='a', order='A', code='', sku='A', product='Product A', qty=100,
                     day='2026-09-16', due='2026-09-16', cups=10, yield_rate=10,
                     line='COOKED', market='domestic', stock_size='M', size='M',
                     locked=False, earliest='', status='unknown', ready_date='', reviewer='',
                     max_qty=0, egg='มีไข่', soup_rank=0, class_groups={}),
            ],
            'lots': [dict(day='2026-09-16', market='domestic', size='M', kg=5)],
            'capacity': {'RAW': 1000, 'COOKED': 1000}, 'forecasts': [], 'operation_rules': (),
        }

        entry = evaluate(context, baseline_rows(context))['schedule'][0]

        self.assertEqual(entry['rm_required_kg'], 10)
        self.assertEqual(entry['rm_allocated_kg'], 5)
        self.assertEqual(entry['rm_shortage_kg'], 5)
        self.assertEqual(entry['rm_coverage'], 0.5)

    def test_bk_run_is_fully_uncovered_when_no_bk_stock_exists(self):
        context = {
            'start': '2026-09-16',
            'settings': {'lookahead': 1, 'adjust_from': '2026-09-16', 'shift_hours': 8,
                         'setup_minutes': 0, 'freeze_percent': None, 'freeze_cost': None,
                         'stop_cost': None},
            'jobs': [
                dict(id='bk', order='BK order', code='', sku='BK', product='BK product', qty=100,
                     day='2026-09-16', due='2026-09-16', cups=10, yield_rate=0,
                     rm_required_kg=8, line='COOKED', market='domestic', stock_size='BK', size='BK',
                     locked=False, earliest='', status='unknown', ready_date='', reviewer='',
                     max_qty=0, egg='มีไข่', soup_rank=0, class_groups={}),
            ],
            'lots': [], 'capacity': {'RAW': 1000, 'COOKED': 1000},
            'forecasts': [], 'operation_rules': (),
        }

        entry = evaluate(context, baseline_rows(context))['schedule'][0]

        self.assertEqual(entry['rm_required_kg'], 8)
        self.assertEqual(entry['rm_allocated_kg'], 0)
        self.assertEqual(entry['rm_shortage_kg'], 8)
        self.assertEqual(entry['rm_coverage'], 0)

    def test_incompatible_allergens_and_earliest_date(self):
        c = self.context()
        c['jobs'][1]['egg']='ไม่มีไข่'
        p = compare(c)[2]
        self.assertFalse(any(r['job']=='b' and r['day']==c['start'] for r in p['rows']))
        c['jobs'][1]['earliest']='2026-09-18'
        self.assertEqual(compare(c)[2]['moved'],0)

    def test_context_signature_changes_with_readiness(self):
        c = self.context()
        before = signature(c)
        c['jobs'][0]['reviewer']='other'
        self.assertNotEqual(before,signature(c))

    def test_raw_capacity_is_separate_and_market_cannot_borrow(self):
        c = self.context()
        c['jobs'][1].update(line='RAW', market='export', egg='ไม่มีไข่')
        c['lots'].append(dict(day=c['start'],market='export',size='M',kg=20))
        c['capacity']['RAW']=1000
        p=compare(c)[2]
        self.assertEqual(p['daily'][0]['hours']['RAW'],8)
        self.assertLess(p['daily'][0]['hours']['COOKED'],8)
        c['lots'].pop()
        self.assertTrue(compare(c)[0]['errors'])

    def test_freeze_cost_is_once_at_boundary(self):
        c=self.context()
        p=compare(c)[0]
        self.assertEqual(p['freeze_cost'],p['remaining']*10)

    def test_unknown_egg_and_forecast_block_review_status(self):
        c=self.context()
        c['jobs'][0]['egg']=''
        self.assertEqual(compare(c)[0]['status'],'conditional')
        c=self.context()
        c['forecasts']=['lot-x']
        self.assertEqual(compare(c)[0]['status'],'conditional')

    def test_store_preserves_approval_and_preferences(self):
        with TemporaryDirectory() as d:
            path=Path(d)/'prefs.json'
            data={'settings':{},'profiles':{'a':{'locked':True}}}
            save_preferences(path,data)
            self.assertEqual(load_preferences(path),data)
            path=Path(d)/'approval.json'
            save_approval(path,{'plan':'a'})
            with self.assertRaises(FileExistsError): save_approval(path,{'plan':'b'})


if __name__=='__main__': unittest.main()
