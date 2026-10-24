import unittest

from monitor.diff import compare, summarize
from monitor.models import Item, fmt_rub


def item(sku, price, stock=True, title=None):
    return Item(sku, title or f'Товар {sku}', f'/p/{sku}', 'Раздел', price, None, stock)


class CompareTest(unittest.TestCase):
    def kinds(self, prev, curr):
        return {c.sku: c.kind for c in compare({i.sku: i for i in prev}, {i.sku: i for i in curr})}

    def test_all_kinds(self):
        prev = [item('down', 1000), item('up', 1000), item('same', 1000), item('gone', 500), item('hid', 700),
                item('shown', None), item('out', 100), item('back', 100, False)]
        curr = [item('down', 900), item('up', 1100), item('same', 1000), item('fresh', 300), item('hid', None),
                item('shown', 800), item('out', 100, False), item('back', 100, True)]
        self.assertEqual(self.kinds(prev, curr), {
            'down': 'price_down', 'up': 'price_up', 'fresh': 'new', 'gone': 'removed', 'hid': 'price_unset',
            'shown': 'price_set', 'out': 'out_of_stock', 'back': 'back_in_stock'})

    def test_no_changes(self):
        self.assertEqual(compare({'a': item('a', 100)}, {'a': item('a', 100)}), [])

    def test_unknown_price_stays_unknown(self):
        self.assertEqual(compare({'a': item('a', None)}, {'a': item('a', None)}), [])

    def test_price_and_stock_at_once_give_two_changes(self):
        ch = compare({'a': item('a', 100)}, {'a': item('a', 90, False)})
        self.assertEqual(sorted(c.kind for c in ch), ['out_of_stock', 'price_down'])

    def test_percent_and_delta(self):
        c = compare({'a': item('a', 1299000)}, {'a': item('a', 999000)})[0]
        self.assertEqual(c.delta_kop, -300000)
        self.assertAlmostEqual(c.pct, -23.0946, places=3)

    def test_sorted_by_kind_then_by_magnitude(self):
        prev = {s: item(s, 10000) for s in 'abc'}
        curr = {'a': item('a', 9900), 'b': item('b', 8000), 'c': item('c', 12000)}
        ch = compare(prev, curr)
        self.assertEqual([(c.kind, c.sku) for c in ch], [('price_down', 'b'), ('price_down', 'a'), ('price_up', 'c')])

    def test_summary(self):
        ch = compare({'a': item('a', 1)}, {'b': item('b', 1)})
        self.assertEqual(dict(summarize(ch)), {'new': 1, 'removed': 1})

    def test_fmt_rub(self):
        self.assertEqual(fmt_rub(6499000), '64 990 ₽')
        self.assertEqual(fmt_rub(129950), '1 299,50 ₽')
        self.assertEqual(fmt_rub(None), '—')


if __name__ == '__main__':
    unittest.main()
