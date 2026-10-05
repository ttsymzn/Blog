#!/usr/bin/env python3
"""Blogger の記事を読み込み、このサイト用の Atom フィード（docs/feed.xml）を作る。

Feedly などのフィードリーダーは docs/feed.xml を定期的に見に来るので、
ブログが更新されるとリーダー側にも新しい記事が表示される。
各記事のリンクはこのサイト内の記事ページ（#post-ID）を指す。
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

BLOG_URL = 'https://70sonan.blogspot.com'
SITE_URL = 'https://ttsymzn.github.io/Blog/'
FEED_URL = SITE_URL + 'feed.xml'
SITE_TITLE = '蘇南高校 校長ブログ'
SITE_SUBTITLE = '長野県蘇南高等学校の校長が、学校の日々の様子をお伝えします。'
MAX_ENTRIES = 50
SUMMARY_LENGTH = 200
OUTPUT = Path(__file__).resolve().parent.parent / 'docs' / 'feed.xml'


def fetch_entries():
    url = f'{BLOG_URL}/feeds/posts/default?alt=json&max-results={MAX_ENTRIES}'
    req = urllib.request.Request(url, headers={'User-Agent': 'sonan-blog-feed-builder'})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.load(res)
    return data['feed'].get('entry', [])


def to_text(markup):
    # 本文の HTML からタグを取り除き、要約用のプレーンテキストにする
    text = re.sub(r'<(script|style)\b.*?</\1>', ' ', markup, flags=re.S | re.I)
    text = re.sub(r'<br\s*/?>|</(p|div|li|h[1-6]|blockquote|tr)>', '\n', text, flags=re.I)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.split('\n')]
    return ' '.join(line for line in lines if line)


def build_entry(entry):
    post_id = entry['id']['$t'].split('post-')[-1]
    title = (entry.get('title') or {}).get('$t') or '（無題）'
    content = (entry.get('content') or entry.get('summary') or {}).get('$t', '')
    summary = to_text(content)
    if len(summary) > SUMMARY_LENGTH:
        summary = summary[:SUMMARY_LENGTH] + '…'
    original = next((l['href'] for l in entry.get('link', []) if l.get('rel') == 'alternate'), BLOG_URL)
    author = ((entry.get('author') or [{}])[0].get('name') or {}).get('$t') or SITE_TITLE
    thumb = (entry.get('media$thumbnail') or {}).get('url')
    if thumb:
        # Blogger のサムネイルは 72px なので大きいサイズに差し替える
        thumb = re.sub(r'/s72(-[a-z]+)*/', '/w640-h360-c/', thumb)
        thumb = re.sub(r'=s72(-[a-z]+)*$', '=w640-h360-c', thumb)
    categories = [c['term'] for c in entry.get('category', []) if c.get('term')]

    parts = [
        '  <entry>',
        f'    <id>{escape(entry["id"]["$t"])}</id>',
        f'    <title>{escape(title)}</title>',
        f'    <link rel="alternate" type="text/html" href={quoteattr(SITE_URL + "#post-" + post_id)}/>',
        f'    <link rel="related" type="text/html" href={quoteattr(original)}/>',
        f'    <published>{escape(entry["published"]["$t"])}</published>',
        f'    <updated>{escape(entry["updated"]["$t"])}</updated>',
        f'    <author><name>{escape(author)}</name></author>',
    ]
    parts += [f'    <category term={quoteattr(c)}/>' for c in categories]
    if thumb:
        parts.append(f'    <media:thumbnail url={quoteattr(thumb)}/>')
    parts += [
        f'    <summary type="text">{escape(summary)}</summary>',
        f'    <content type="html">{escape(content)}</content>',
        '  </entry>',
    ]
    return '\n'.join(parts), entry['updated']['$t']


def build_feed(entries):
    entries = sorted(entries, key=lambda e: e['published']['$t'], reverse=True)
    built = [build_entry(e) for e in entries]
    # 生成のたびに中身が変わらないよう、フィードの更新日時は記事の最終更新日時を使う
    updated = max((u for _, u in built), default='1970-01-01T00:00:00Z')
    head = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xml:lang="ja">',
        f'  <id>{escape(SITE_URL)}</id>',
        f'  <title>{escape(SITE_TITLE)}</title>',
        f'  <subtitle>{escape(SITE_SUBTITLE)}</subtitle>',
        f'  <link rel="alternate" type="text/html" href={quoteattr(SITE_URL)}/>',
        f'  <link rel="self" type="application/atom+xml" href={quoteattr(FEED_URL)}/>',
        f'  <updated>{escape(updated)}</updated>',
        f'  <author><name>{escape(SITE_TITLE)}</name></author>',
    ]
    return '\n'.join(head + [e for e, _ in built] + ['</feed>']) + '\n'


def main():
    if len(sys.argv) > 1:
        # テスト用：保存しておいた JSON から作る
        entries = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['feed'].get('entry', [])
    else:
        entries = fetch_entries()
    feed = build_feed(entries)
    if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == feed:
        print('feed.xml は最新です')
        return
    OUTPUT.write_text(feed, encoding='utf-8')
    print(f'feed.xml を更新しました（{len(entries)} 件）')


if __name__ == '__main__':
    main()
