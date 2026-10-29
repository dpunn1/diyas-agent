import csv, gzip, json, math, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, 'articles', 'all.jsonl.gz')
INDEX = os.path.join(HERE, 'index.json')
PROFILE = os.path.join(HERE, 'profile.json')
QUESTIONS = os.path.join(HERE, 'questions.csv')
TARGET = 27
STOP = set('a an and are as at be by for from has have in is it its of on or that the to was were with this which who'.split())


def tokens(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP]


def build_index():
    arts = []
    with gzip.open(ARCHIVE, 'rt', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            a = json.loads(line)
            body = Counter(tokens(a.get('en') or '')) + Counter(tokens(a.get('simple') or ''))
            arts.append({'id': a['id'], 'title': a['title'], 'subject': a['subject'],
                         'title_terms': tokens(a['title']), 'terms': dict(body)})
    with open(INDEX, 'w', encoding='utf-8') as f:
        json.dump(arts, f)
    return arts


def load_index():
    if not os.path.exists(INDEX):
        return build_index()
    with open(INDEX, encoding='utf-8') as f:
        return json.load(f)


def load_profile():
    try:
        with open(PROFILE, encoding='utf-8') as f:
            p = json.load(f)
    except FileNotFoundError:
        p = {}
    return list(p.get('subjects', [])), int(p.get('results', 5))


def rank(query, arts, subjects):
    q = tokens(query)
    if not q:
        return []
    qset = set(q)
    # inverse document frequency: a query word that is rare across articles weighs more
    # in the title match only; body counts stay as they were, so long articles are not penalised
    n_docs = len(arts)
    df = dict.fromkeys(qset, 0)
    for a in arts:
        for t in df:
            if t in a['title_terms']:
                df[t] += 1
    idf = {t: math.log((n_docs + 1) / (df[t] + 1)) + 1 for t in qset}
    scored = []
    for a in arts:
        tt = a['title_terms']
        s = 0
        for t in q:
            s += 10 * idf[t] * (t in tt) + a['terms'].get(t, 0)
        if tt:
            matched = sum(1 for t in tt if t in qset)
            s += 5 * matched
            # every word of the title is in the query: a big bonus, scaled by title length,
            # so an exact title beats a longer or broader title that only shares some words
            if matched == len(tt):
                s += 50 * len(tt)
        if s > 0:
            pref = subjects.index(a['subject']) if a['subject'] in subjects else len(subjects)
            scored.append((-s, pref, a['id'], a))
    scored.sort(key=lambda x: x[:3])
    return [x[3] for x in scored]


def get_article(aid):
    with gzip.open(ARCHIVE, 'rt', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            a = json.loads(line)
            if a['id'] == aid:
                return a
    return None


def first_para(text):
    for line in (text or '').splitlines():
        if line.strip():
            return line.strip()
    return ''


def cmd_search(query):
    subjects, n = load_profile()
    hits = rank(query, load_index(), subjects)[:n]
    if not hits:
        return 0
    for i, a in enumerate(hits, 1):
        print('%d. %s (%s)' % (i, a['title'], a['subject']))
    if not sys.stdin.isatty():
        return 0
    print('Read which? [1-%d, Enter for none] ' % len(hits), end='', flush=True)
    try:
        choice = input().strip()
    except EOFError:
        return 0
    if choice.isdigit() and 1 <= int(choice) <= len(hits):
        pick = hits[int(choice) - 1]
        art = get_article(pick['id'])
        if art:
            print(first_para(art.get('simple')) or first_para(art.get('en')))
            print('%s (%s)' % (art['title'], art['subject']))
    return 0


def cmd_score():
    arts = load_index()
    covered = total = 0
    with open(QUESTIONS, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            total += 1
            hits = rank(row['question'], arts, [])
            first = hits[0]['title'] if hits else '(no result)'
            if first.casefold() == row['answer'].strip().casefold():
                covered += 1
            else:
                print('MISS: %s | answer: %s | first: %s' % (row['question'], row['answer'], first))
    verdict = 'PASS' if covered >= TARGET else 'below target'
    print('%d of %d covered: %s' % (covered, total, verdict))
    return 0 if covered >= TARGET else 1


def main(argv):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if len(argv) >= 3 and argv[1] == 'search':
        return cmd_search(' '.join(argv[2:]))
    if len(argv) == 2 and argv[1] == 'score':
        return cmd_score()
    print('usage: python pedia.py search <query> | score')
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
