import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import main


class FakeProductDatabase:
    def __init__(self, products):
        self.products = products
        self.calls = []

    def search_by_attributes(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get('style') == 'office':
            return self.products
        return []

    def get_product_by_id(self, product_id):
        for product in self.products:
            if product.get('id') == product_id:
                return product
        return None


class FakeQwen:
    def __init__(self, outfits=None):
        self.outfits = outfits or []
        self.last_analyze = None
        self.last_generate = None

    def analyze_query(self, user_query, user_image=None, budget=None, sizes=None):
        self.last_analyze = {
            'user_query': user_query,
            'user_image': user_image,
            'budget': budget,
            'sizes': sizes,
        }
        return {
            'style': 'office',
            'colors': ['black'],
            'budget': budget,
            'category': 'full_outfit',
            'occasion': 'work',
            'sizes': sizes or ['M'],
        }

    def generate_outfit_recommendations(self, style_intent, available_products):
        self.last_generate = {
            'style_intent': style_intent,
            'available_products': available_products,
        }
        return self.outfits


class FakeCombiner:
    def create_outfits(self, products, style='casual', max_budget=None, num_outfits=3):
        if not products:
            return []
        product = products[0]
        return [
            {
                'name': 'Fallback outfit',
                'style': style,
                'items': [product],
                'total_price': product.get('price', 0),
                'description': 'Fallback',
                'source': 'combiner',
            }
        ]


class MainApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.products = [
            {
                'id': 'top-1',
                'name': 'Shirt',
                'price': 2500,
                'currency': 'KZT',
                'url': 'https://example.com/top-1',
                'image_url': 'https://example.com/top-1.jpg',
                'category': 'tops',
                'outfit_category': 'top',
                'colors': ['black'],
                'sizes': ['M', 'L'],
            },
            {
                'id': 'bottom-1',
                'name': 'Trousers',
                'price': 3000,
                'currency': 'KZT',
                'url': 'https://example.com/bottom-1',
                'image_url': 'https://example.com/bottom-1.jpg',
                'category': 'bottoms',
                'outfit_category': 'bottom',
                'colors': ['black'],
                'sizes': ['M', 'L'],
            },
        ]

    def test_query_json_flow_uses_budget(self):
        fake_db = FakeProductDatabase(self.products)
        fake_qwen = FakeQwen(
            outfits=[
                {
                    'name': 'Office look',
                    'style': 'office',
                    'items': [self.products[0], self.products[1]],
                    'total_price': 5500,
                    'description': 'Office-ready',
                    'source': 'qwen',
                }
            ]
        )

        with patch.object(main, 'get_product_db', return_value=fake_db), \
            patch.object(main, 'get_qwen_chatbot', return_value=fake_qwen), \
            patch.object(main, 'get_outfit_combiner', return_value=FakeCombiner()):
            response = self.client.post(
                '/api/v1/stylist/query',
                json={'query': 'office outfit', 'budget': 5000, 'sizes': ['M']},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(len(payload['outfits']), 1)
        self.assertEqual(fake_qwen.last_analyze['budget'], 5000)
        self.assertEqual(fake_qwen.last_analyze['sizes'], ['M'])
        self.assertEqual(fake_db.calls[0]['budget'], (0, 5000))

    def test_query_multipart_with_image(self):
        fake_db = FakeProductDatabase(self.products)
        fake_qwen = FakeQwen(outfits=[])
        image = Image.new('RGB', (8, 8), color='white')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)

        with patch.object(main, 'get_product_db', return_value=fake_db), \
            patch.object(main, 'get_qwen_chatbot', return_value=fake_qwen), \
            patch.object(main, 'get_outfit_combiner', return_value=FakeCombiner()):
            response = self.client.post(
                '/api/v1/stylist/query',
                data={'query': 'office outfit', 'budget': '5000', 'sizes': 'M'},
                files={'image': ('look.png', buffer.getvalue(), 'image/png')},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertIsNotNone(fake_qwen.last_analyze['user_image'])
        self.assertEqual(fake_qwen.last_analyze['sizes'], ['M'])

    def test_query_returns_no_match_when_catalog_empty(self):
        fake_db = FakeProductDatabase([])
        fake_qwen = FakeQwen()

        with patch.object(main, 'get_product_db', return_value=fake_db), \
            patch.object(main, 'get_qwen_chatbot', return_value=fake_qwen), \
            patch.object(main, 'get_outfit_combiner', return_value=FakeCombiner()):
            response = self.client.post('/api/v1/stylist/query', json={'query': 'office outfit'})

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload['success'])
        self.assertEqual(payload['outfits'], [])


if __name__ == '__main__':
    unittest.main()
