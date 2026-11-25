"""RAG hibrit arama düzeltmelerinin testleri (sohbet kalite teşhisi sonrası).

Kapsam:
  - _build_fts_match_query AND/OR üretimi
  - search(): model filtresi (farklı model vektörleriyle kıyaslama yapılmaz)
  - search(): AND -> OR fallback
  - search(): mean-centering (ilgisiz vektörlerin skoru ~0'a iner)
Sahte db ile çalışır; ağ ve gerçek veritabanı kullanılmaz.
"""
import json
import time
import unittest

import backend.rag_index as ri


class HybridFakeDB:
    """RagIndex.search SQL yüzeyinin kaydedici sahtesi."""

    def __init__(self, embed_count=11, fts_count=50):
        self.embed_count = embed_count
        self.fts_count = fts_count
        self.captured = []          # (sql_normalized, params)
        self.fts_match_params = []  # sirayla denenen MATCH sorgulari

    def execute_query(self, sql, params=None):
        norm = ' '.join(sql.split())
        self.captured.append((norm, params))

        if 'COUNT(*) FROM function_embeddings' in norm:
            return [(self.embed_count,)]
        if 'SELECT function_id, embedding FROM function_embeddings' in norm:
            # f1 sorgu vektörüne yakin, digeri ilgisiz yonde
            rows = [(1, json.dumps([1.0, 0.0]))]
            rows += [(fid, json.dumps([0.0, 1.0])) for fid in range(2, 12)]
            return rows
        if 'COUNT(*) FROM fts_functions' in norm:
            return [(self.fts_count,)]
        if 'bm25(fts_functions)' in norm:
            match_query = (params or [None])[0]
            self.fts_match_params.append(match_query)
            if ' OR ' in (match_query or ''):
                return [(2, -8.0)]  # OR denemesinde eslesme var
            return []               # AND bos doner
        if 'FROM functions f' in norm:
            out = []
            for fid in (params or []):
                if fid == 1:
                    out.append({'id': 1, 'function_name': 'sendDocumentFile', 'class_name': 'EHacizSkeleton',
                                'package_name': 'p', 'signature': '', 'ai_summary': 's1'})
                elif fid == 2:
                    out.append({'id': 2, 'function_name': 'otherFunc', 'class_name': 'Foo',
                                'package_name': 'p', 'signature': '', 'ai_summary': 's2'})
                else:
                    out.append({'id': fid, 'function_name': f'fn{fid}', 'class_name': 'X',
                                'package_name': 'p', 'signature': '', 'ai_summary': ''})
            return out
        return []


class TestFtsQueryBuilder(unittest.TestCase):
    def test_and_mode_quotes_tokens(self):
        q = ri._build_fts_match_query('sendDocumentFile islemiyor')
        self.assertEqual(q, '"sendDocumentFile" AND "islemiyor"')

    def test_or_mode_joins_with_or(self):
        q = ri._build_fts_match_query('sendDocumentFile islemiyor', mode='OR')
        self.assertEqual(q, '"sendDocumentFile" OR "islemiyor"')

    def test_empty_returns_none(self):
        self.assertIsNone(ri._build_fts_match_query(''))


class TestHybridSearch(unittest.TestCase):
    def setUp(self):
        self.original_db = ri.db
        self.fake_db = HybridFakeDB()
        ri.db = self.fake_db
        self.addCleanup(lambda: setattr(ri, 'db', self.original_db))

        self.original_cache = dict(ri._RUNTIME_SETTINGS_CACHE)
        ri._RUNTIME_SETTINGS_CACHE['value'] = {
            'provider': 'llamacpp',
            'api_url': 'http://chat:1234/v1',
            'api_key': '',
            'embedding_api_url': '',
            'embedding_model': 'model-x',
            'embedding_api_key': '',
        }
        ri._RUNTIME_SETTINGS_CACHE['expires_at'] = time.time() + 60
        self.addCleanup(lambda: (ri._RUNTIME_SETTINGS_CACHE.clear(),
                                 ri._RUNTIME_SETTINGS_CACHE.update(self.original_cache)))

        self.original_embed = ri._get_embedding
        ri._get_embedding = lambda text, session=None: [0.9, 0.1]
        self.addCleanup(lambda: setattr(ri, '_get_embedding', self.original_embed))

    def _search(self):
        return ri.RagIndex.search(16, 'sendDocumentFile ne işe yarıyor', limit=5)

    def test_stored_vectors_filtered_by_current_model(self):
        self._search()
        stored_sqls = [c for c in self.fake_db.captured
                       if 'SELECT function_id, embedding FROM function_embeddings' in c[0]]
        self.assertTrue(stored_sqls, 'vektor sorgusu calismadi')
        sql, params = stored_sqls[0]
        self.assertIn('model_name = ?', sql)
        self.assertEqual(list(params), [16, 'model-x'])

    def test_and_query_falls_back_to_or(self):
        self._search()
        self.assertEqual(len(self.fake_db.fts_match_params), 2)
        self.assertIn(' AND ', self.fake_db.fts_match_params[0])
        self.assertIn(' OR ', self.fake_db.fts_match_params[1])

    def test_mean_centering_zeroes_unrelated_vectors(self):
        hits = {h['id']: h for h in self._search()}
        # f1: query'e yakin vektor -> en yuksek skor
        # f2: yalniz FTS eslesmesi (bm25 en iyi -> 0.4 katkisi)
        self.assertGreater(hits[1]['score'], hits[2]['score'])
        # Ilgisiz vektörler (sim = ortalama) ~0'a inmeli; eskiden ~0.06 tavan vardi
        unrelated = [h for fid, h in hits.items() if fid not in (1, 2)]
        for h in unrelated:
            self.assertLess(h['score'], 0.001)

    def test_exact_lexical_hit_outranks_vector_noise(self):
        # mean-centering + relatif bm25 olmadan vektor gürültüsü (düz taban cosine)
        # birebir isim eslesmesini ezerdi; simdi f2 listede anlamlı skorla var
        hits = {h['id']: h for h in self._search()}
        self.assertIn(2, hits)
        self.assertAlmostEqual(hits[2]['score'], 0.4, places=2)


if __name__ == '__main__':
    unittest.main()
