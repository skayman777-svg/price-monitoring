import unittest

from monitor.parse import clean, parse_listing, parse_price

HTML = """
<html><body>
<div class="promo-banner">Аксессуары за 990&nbsp;₽</div>
<section>
  <article class="product-card" data-sku="A-1">
    <a class="product-card__title" href="/product/a-1/">
       Ноутбук  &quot;Тест&quot; &amp; сумка
       (16 ГБ)
    </a>
    <div class="product-card__prices">
      <span class="price price--old">74&nbsp;990&nbsp;₽</span>
      <span class="price price--current">64&nbsp;990&nbsp;₽</span>
    </div>
    <div class="stock stock--in">В наличии</div>
  </article>
  <article class="product-card product-card--out" data-sku="A-2">
    <a class="product-card__title" href="/product/a-2/">Смартфон</a>
    <div class="product-card__prices"><span class="price price--current"><small>от</small> 8&#8239;990&nbsp;₽</span></div>
    <div class="stock stock--out">Нет в наличии</div>
  </article>
  <article class="product-card" data-sku="A-3">
    <a class="product-card__title" href="/product/a-3/">Ноутбук Макс</a>
    <div class="product-card__prices"><span class="price price--ask">Цена по запросу</span></div>
    <div class="stock stock--in">В наличии</div>
  </article>
  <article class="product-card" data-sku="A-4">
    <a class="product-card__title" href="/product/a-4/">Карточка без цены</a>
    <div class="product-card__prices"></div>
    <div class="stock stock--soon">Ожидается поставка</div>
  </article>
  <article class="product-card"><a class="product-card__title" href="/x/">Без артикула</a></article>
</section>
<aside class="reco"><div class="reco-item"><a href="/product/zz/">Рекомендация</a><span class="price price--current">1&nbsp;000&nbsp;₽</span></div></aside>
<nav class="pagination"><a class="pagination__next" href="/catalog/x/?page=2">Далее →</a></nav>
</body></html>
"""


class ParsePriceTest(unittest.TestCase):
    def test_formats(self):
        cases = {
            '64 990 ₽': 6499000,
            '64 990 ₽': 6499000,
            'от 8 990 ₽': 899000,
            '12 490 ₽': 1249000,
            '1 299,90 ₽': 129990,
            '1 299,5 руб.': 129950,
            '2490.00': 249000,
            '0 ₽': 0,
            'Цена по запросу': None,
            '': None,
            None: None,
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_price(text), want)

    def test_clean(self):
        self.assertEqual(clean('  a\n\t b c  '), 'a b c')


class ParseListingTest(unittest.TestCase):
    def setUp(self):
        self.items, self.next_url, self.warnings = parse_listing(HTML, 'http://shop.test/catalog/x/', 'Раздел')
        self.by = {i.sku: i for i in self.items}

    def test_only_product_cards(self):
        self.assertEqual(sorted(self.by), ['A-1', 'A-2', 'A-3', 'A-4'])      # баннер и рекомендации не тронуты

    def test_normal_card(self):
        a = self.by['A-1']
        self.assertEqual(a.title, 'Ноутбук "Тест" & сумка (16 ГБ)')
        self.assertEqual((a.price_kop, a.old_price_kop, a.in_stock, a.note), (6499000, 7499000, True, ''))
        self.assertEqual(a.url, 'http://shop.test/product/a-1/')
        self.assertEqual(a.category, 'Раздел')

    def test_from_price_and_out_of_stock(self):
        b = self.by['A-2']
        self.assertEqual((b.price_kop, b.in_stock, b.note), (899000, False, 'цена «от»'))

    def test_price_on_request(self):
        c = self.by['A-3']
        self.assertEqual((c.price_kop, c.note), (None, 'цена по запросу'))

    def test_broken_card_is_kept_with_warning(self):
        d = self.by['A-4']
        self.assertEqual((d.price_kop, d.in_stock, d.note), (None, False, 'цена не найдена'))
        self.assertTrue(any('A-4' in w for w in self.warnings))

    def test_card_without_sku_is_skipped_with_warning(self):
        self.assertTrue(any('карточка №5 пропущена' in w for w in self.warnings))

    def test_next_page(self):
        self.assertEqual(self.next_url, 'http://shop.test/catalog/x/?page=2')

    def test_no_next_page(self):
        _, nxt, _ = parse_listing('<html></html>', 'http://shop.test/', 'X')
        self.assertIsNone(nxt)


if __name__ == '__main__':
    unittest.main()
