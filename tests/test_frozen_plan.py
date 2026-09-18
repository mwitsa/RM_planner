import unittest
from rm_planner.planning.alternatives import compare, evaluate, baseline_rows, signature


def context():
    job = dict(id='a', order='A', code='A', sku='A', product='A', qty=100,
               day='2026-09-16', due='2026-10-01', cups=100, yield_rate=10,
               line='RAW', market='domestic', stock_size='SS', size='SS',
               locked=False, earliest='', status='unknown', ready_date='',
               reviewer='', max_qty=0, egg='egg', soup_rank=0, class_groups={})
    return dict(start='2026-09-16',
                settings=dict(lookahead=1, adjust_from='2026-09-16', shift_hours=8,
                              setup_minutes=30, stop_cost=100, freeze_cost=52),
                jobs=[job], capacity={'RAW': 800, 'COOKED': 800},
                lots=[dict(day='2026-09-15', market='domestic', size='SS', kg=20,
                           is_stock=True),
                      dict(day='2026-09-16', market='domestic', size='SS', kg=6)])


class FrozenPlanTests(unittest.TestCase):
    def test_only_balanced_tops_up_whole_order(self):
        c = context()
        base, material, balanced = compare(c)
        self.assertEqual(base['schedule'][0]['rm_shortage_kg'], 4)
        self.assertEqual(material['rows'], [])
        self.assertEqual(len(balanced['rows']), 1)
        entry = balanced['schedule'][0]
        self.assertEqual(entry['qty'], 100)
        self.assertEqual(entry['rm_fresh_kg'], 6)
        self.assertEqual(entry['rm_frozen_kg'], 4)
        self.assertEqual(entry['rm_shortage_kg'], 0)
        self.assertEqual(balanced['remaining'], 0)
        self.assertEqual(balanced['signature'], signature(c))
        self.assertNotIn('allow_frozen_stock', c)

    def test_frozen_pool_respects_market_size_date_and_quantity(self):
        for update in ({'market': 'export'}, {'size': 'M'}, {'day': '2026-09-17'}):
            with self.subTest(update=update):
                c = context()
                c['lots'][0].update(update)
                p = evaluate(dict(c, allow_frozen_stock=True), baseline_rows(c))
                self.assertEqual(p['schedule'][0]['rm_shortage_kg'], 4)
        c = context()
        c['lots'][0]['kg'] = 2
        p = evaluate(dict(c, allow_frozen_stock=True), baseline_rows(c))
        self.assertEqual(p['schedule'][0]['rm_frozen_kg'], 2)
        self.assertEqual(p['schedule'][0]['rm_shortage_kg'], 2)

    def test_chilled_arrivals_become_freeze_on_boundary(self):
        c = context()
        c['lots'] = [dict(day=c['start'], market='domestic', size='SS',
                          kg=10, freeze_day=c['start'])]
        self.assertEqual(evaluate(c, baseline_rows(c))['schedule'][0]['rm_shortage_kg'], 10)
        p = evaluate(dict(c, allow_frozen_stock=True), baseline_rows(c))
        self.assertEqual(p['schedule'][0]['rm_frozen_kg'], 10)

    def test_no_double_spending_frozen_stock(self):
        c = context()
        c['lots'][0]['kg'] = 5
        c['jobs'].append(dict(c['jobs'][0], id='b'))
        p = evaluate(dict(c, allow_frozen_stock=True), baseline_rows(c))
        self.assertEqual(sum(e['rm_frozen_kg'] for e in p['schedule']), 5)
        self.assertEqual(sum(e['rm_shortage_kg'] for e in p['schedule']), 9)
