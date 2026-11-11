"""Citizen voices: YouTube, Reddit and X readers against fake HTTP (no network, fake keys); the digest never
carries a username or a key. Run: python3 -m unittest tests.test_voices"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.voices import analyse, reddit, themes, x, youtube  # noqa: E402
from pipeline.voices import __main__ as cli  # noqa: E402
from pipeline.voices.model import Post, Skipped  # noqa: E402

YT_KEY, RD_SECRET, X_TOKEN = 'FAKE-YT-KEY-zzz', 'FAKE-REDDIT-SECRET-zzz', 'FAKE-X-TOKEN-zzz'


class Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.content = payload, status, b'x'

    def json(self):
        return self._p


class FakeHTTP:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _serve(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for needle, payload in self.routes:
            if needle in url:
                return payload(kw) if callable(payload) else payload
        return Resp({}, 404)

    def get(self, url, **kw):
        return self._serve('GET', url, **kw)

    def post(self, url, **kw):
        return self._serve('POST', url, **kw)


def yt_comment(cid, text, likes=1, author='UCauthor1', name='Real Person'):
    return {'id': cid, 'snippet': {'totalReplyCount': 2, 'topLevelComment': {'id': cid, 'snippet': {
        'textDisplay': text, 'likeCount': likes, 'authorDisplayName': name, 'authorChannelId': {'value': author},
        'publishedAt': '2026-09-01T10:00:00Z'}}}}


class YouTubeTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHTTP([
            ('/search', Resp({'items': [{'id': {'videoId': 'vid00000001'}, 'snippet': {
                'title': 'Power cuts: people speak', 'channelTitle': 'Some TV', 'channelId': 'UCtv'}}]})),
            ('/videos', Resp({'items': [{'id': 'vid00000001', 'snippet': {
                'title': 'Power cuts: people speak', 'channelTitle': 'Some TV', 'channelId': 'UCtv'},
                'statistics': {'viewCount': '9000', 'commentCount': '3'}}]})),
            ('/commentThreads', Resp({'items': [
                yt_comment('c1', 'Daily power cut in our area for three hours, TVK government must act', 40),
                yt_comment('c2', 'மின்வெட்டு தினமும் நடக்கிறது, அரசு என்ன செய்கிறது என்று தெரியவில்லை', 12, 'UCauthor2'),
                yt_comment('c3', 'Thanks for watching, subscribe to our channel for more TVK news', 99, 'UCtv')]})),
        ])

    def test_pull_reads_comments_with_key_in_header_only(self):
        with mock.patch.dict(os.environ, {'YOUTUBE_API_KEY': YT_KEY}):
            posts, note = youtube.pull({'queries': ['power cut'], 'max_units': 300}, '2026-05-10', '2026-11-10',
                                       'salt', session=self.http)
        self.assertEqual([p.id for p in posts], ['c1', 'c2'])     # the channel's own comment is dropped
        self.assertEqual(note['units_used'], 102)                  # search 100 + videos 1 + comments 1
        for _, url, kw in self.http.calls:
            self.assertNotIn(YT_KEY, url)
            self.assertNotIn(YT_KEY, json.dumps(kw.get('params', {})))
            self.assertEqual(kw['headers']['X-Goog-Api-Key'], YT_KEY)
        self.assertNotIn('UCauthor1', posts[0].author_key)
        self.assertTrue(posts[0].url.endswith('&lc=c1'))

    def test_budget_stops_calls(self):
        with mock.patch.dict(os.environ, {'YOUTUBE_API_KEY': YT_KEY}):
            posts, note = youtube.pull({'queries': ['a', 'b', 'c'], 'max_units': 100}, '2026-05-10', None, 's',
                                       session=self.http)
        self.assertEqual(sum('/search' in c[1] for c in self.http.calls), 1)
        self.assertEqual(posts, [])
        self.assertLessEqual(note['units_used'], 100)

    def test_no_key_is_skipped(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Skipped):
                youtube.pull({'queries': ['a']}, '2026-05-10', None, 's', session=self.http)


class RedditTests(unittest.TestCase):
    def setUp(self):
        listing = {'data': {'children': [
            {'data': {'id': 'p1', 'title': 'Six months of TVK government: your honest view?', 'selftext': 'Power cuts are worse here.',
                      'author': 'some_user', 'score': 120, 'num_comments': 2, 'created_utc': 1790000000,
                      'permalink': '/r/TamilNadu/comments/p1/x/', 'subreddit': 'TamilNadu'}},
            {'data': {'id': 'old', 'title': 'Old thread about the DMK government', 'author': 'u2', 'score': 5,
                      'num_comments': 0, 'created_utc': 1600000000, 'permalink': '/r/TamilNadu/comments/old/x/'}}]}}
        thread = [{}, {'data': {'children': [
            {'kind': 't1', 'data': {'id': 'k1', 'body': 'Roads in my ward got fixed within a month of the new government, credit where due.',
                                    'author': 'user_a', 'score': 30, 'created_utc': 1790001000,
                                    'permalink': '/r/TamilNadu/comments/p1/x/k1/', 'replies': {'data': {'children': [
                                        {'kind': 't1', 'data': {'id': 'k2', 'body': 'Still waiting for the 2500 they promised women, nothing so far.',
                                                                'author': 'user_b', 'score': 9, 'created_utc': 1790002000,
                                                                'permalink': '/r/TamilNadu/comments/p1/x/k2/', 'replies': ''}}]}}}},
            {'kind': 't1', 'data': {'id': 'k3', 'body': 'I am a bot', 'author': 'AutoModerator', 'score': 1}}]}}]
        self.http = FakeHTTP([('access_token', Resp({'access_token': 'tok-abc'})), ('/search', Resp(listing)),
                              ('/comments/p1', Resp(thread))])

    def test_pull_threads_and_comments(self):
        env = {'REDDIT_CLIENT_ID': 'cid', 'REDDIT_CLIENT_SECRET': RD_SECRET, 'REDDIT_USERNAME': 'idly_news'}
        with mock.patch.dict(os.environ, env):
            posts, note = reddit.pull({'subreddits': ['TamilNadu', 'bad name!'], 'queries': ['TVK government'],
                                       'sorts': ['top']}, '2026-05-10', '2026-11-10', 'salt', session=self.http, pause=0)
        self.assertEqual(sorted(p.id for p in posts), ['k1', 'k2', 'p1'])      # out-of-window post and bot dropped
        self.assertEqual(note['threads_found'], 1)
        gets = [c for c in self.http.calls if c[0] == 'GET']
        self.assertTrue(all(c[1].startswith('https://oauth.reddit.com/') for c in gets))
        self.assertTrue(all('by /u/idly_news' in c[2]['headers']['User-Agent'] for c in gets))
        self.assertTrue(all(RD_SECRET not in c[1] and RD_SECRET not in json.dumps(c[2].get('params', {})) for c in self.http.calls))

    def test_no_key_is_skipped(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Skipped):
                reddit.pull({'subreddits': ['TamilNadu'], 'queries': ['x']}, '2026-05-10', None, 's', session=self.http)


class XTests(unittest.TestCase):
    def test_off_by_default_and_capped(self):
        http = FakeHTTP([('search/recent', Resp({'data': [{'id': '1', 'text': 'TVK government has done nothing about the power cuts here',
                                                           'author_id': '9', 'public_metrics': {'like_count': 3}}]}))])
        with mock.patch.dict(os.environ, {'X_BEARER_TOKEN': X_TOKEN}, clear=True):
            with self.assertRaises(Skipped):
                x.pull({'queries': ['TVK'], 'max_posts': 50}, '2026-05-10', None, 's', session=http)
        with mock.patch.dict(os.environ, {'X_BEARER_TOKEN': X_TOKEN, 'VOICES_X_ENABLED': 'true'}, clear=True):
            with self.assertRaises(Skipped):
                x.pull({'queries': ['TVK'], 'max_posts': 0}, '2026-05-10', None, 's', session=http)
            self.assertEqual(http.calls, [])
            posts, note = x.pull({'queries': ['TVK', 'Vijay'], 'max_posts': 1}, '2026-05-10', None, 's', session=http)
        self.assertEqual((len(posts), note['posts_read'], len(http.calls)), (1, 1, 1))
        self.assertNotIn(X_TOKEN, http.calls[0][1])


def post(i, text, author='a', likes=0, platform='youtube', ctx='v1'):
    return Post(platform=platform, kind='comment', id=str(i), url=f'https://example.org/{i}', text=text,
                author_key=author, likes=likes, context='TVK government six months', context_url=ctx, context_owner='Some TV')


class AnalyseTests(unittest.TestCase):
    def test_themes_and_language(self):
        self.assertIn('power', themes.tag('தினமும் மின்வெட்டு'))
        self.assertIn('women_aid', themes.tag('where is the 2500 for women'))
        self.assertEqual(themes.language('தினமும் மின்வெட்டு நடக்கிறது'), 'ta')
        self.assertEqual(themes.language('namma area la current illa, romba kashtam'), 'ta-latn')
        self.assertEqual(themes.language('The roads are better now'), 'en')

    def test_digest_drops_copy_paste_and_never_names_anyone(self):
        spam = 'TVK government is the best government ever in the history of Tamil Nadu, vote TVK again and again'
        raw = [post(1, 'Daily power cut for three hours in Perambur, @some_handle said the same', 'a', 50),
               post(2, 'Power cut again today, the TVK government should fix TANGEDCO first', 'b', 5),
               post(3, 'Power cuts every evening, second comment from the same person here', 'a', 40),
               post(4, spam, 'c'), post(5, spam, 'd'), post(6, spam, 'e'),
               post(7, 'short', 'f'), post(1, 'duplicate id is ignored entirely by the prepare step', 'g'),
               post(8, 'A long comment about a cricket match that has nothing to do with the topic at all', 'h', ctx='v2')]
        raw[-1].context = 'IPL highlights'
        posts = analyse.prepare(raw, must_match=['tvk', 'government'])
        d = analyse.digest({'slug': 't', 'title': 'T', 'since': '2026-05-10'}, posts, {'youtube': {'units_used': 3}, 'reddit': 'skipped: no key'})
        self.assertEqual(d['totals']['posts_counted'], 3)
        self.assertEqual(d['repeated_text']['posts'], 3)
        power = next(r for r in d['themes'] if r['key'] == 'power')
        self.assertEqual((power['people'], power['posts']), (2, 3))
        self.assertEqual(len(power['top']), 2)                      # one excerpt per person
        text = json.dumps(d, ensure_ascii=False) + analyse.markdown(d)
        self.assertNotIn('some_handle', text)
        self.assertIn('not a poll', text)
        self.assertTrue(all(len(x['text']) <= analyse.EXCERPT for r in d['themes'] for x in r['top']))

    def test_run_reports_skips_and_topic_file_is_valid(self):
        topic = cli.load_topic('tvk-six-months')
        self.assertEqual(topic['x']['max_posts'], 0)                # X stays unpaid until Rahul says yes
        with mock.patch.dict(os.environ, {}, clear=True):
            d = cli.run(topic)
        self.assertEqual(d['totals']['posts_counted'], 0)
        self.assertTrue(all(str(v).startswith('skipped') for v in d['platform_notes'].values()))


if __name__ == '__main__':
    unittest.main()
