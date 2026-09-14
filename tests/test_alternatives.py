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
