"""
Chapter HTML template renderer for realmsandroads.com.
Generates static HTML files matching the existing chapter page format exactly.
"""
import json
import os
import html as _html


# Hardcoded series for the three existing books. New books are added via
# data/series_config.json (written by the + New Work flow).
_SERIES_CONFIG_HARDCODED = {
    'ROTRQ': {
        'name':       'Rise of the Rain Queen',
        'slug':       'rise-of-the-rain-queen',
        'abbrev':     'rotrq',
        'genre':      'Epic Fantasy',
        'series_url': '/series/rise-of-the-rain-queen.html',
        'img_prefix': 'rotrq',
    },
    'OAO': {
        'name':       'Outlaws and Outcasts',
        'slug':       'outlaws-and-outcasts',
        'abbrev':     'oao',
        'genre':      'Epic Fantasy',
        'series_url': '/series/outlaws-and-outcasts.html',
        'img_prefix': 'oao',
    },
    'MOSAS': {
        'name':       'Man of Stone and Shadow',
        'slug':       'man-of-stone-and-shadow',
        'abbrev':     'mosas',
        'genre':      'Sci-Fi / Fantasy',
        'series_url': '/series/man-of-stone-and-shadow.html',
        'img_prefix': 'mosas',
    },
}

# Kept for any direct imports elsewhere — always returns the merged config.
SERIES_CONFIG = _SERIES_CONFIG_HARDCODED


def get_series_config():
    """
    Return the merged SERIES_CONFIG: hardcoded entries + user-added entries
    from data/series_config.json. Safe to call at any time.
    """
    try:
        data_dir        = os.path.join(os.path.dirname(__file__), '..', 'data')
        series_cfg_path = os.path.join(data_dir, 'series_config.json')
        with open(series_cfg_path, 'r', encoding='utf-8') as f:
            extra = json.load(f)
    except (FileNotFoundError, ValueError):
        extra = {}

    merged = dict(_SERIES_CONFIG_HARDCODED)
    merged.update(extra)
    return merged


def derive_chapter_meta(entry):
    book   = entry['book']
    series = get_series_config()[book]
    n      = entry['chapter_number']
    abbrev = series['abbrev']

    chapter_id   = f"{abbrev}-{n}"
    chapter_slug = f"{series['slug']}-chapter-{n}"
    chapter_url  = f"/chapters/{chapter_slug}.html"
    image_name   = f"{abbrev}-ch{n}-header.jpg"

    return {
        'chapter_id':   chapter_id,
        'chapter_slug': chapter_slug,
        'chapter_url':  chapter_url,
        'image_name':   image_name,
        'series':       series,
    }


def get_prev_next(entry, pipeline):
    """Return (prev_entry, next_entry) for same book, by chapter_number."""
    book      = entry['book']
    n         = entry['chapter_number']
    same_book = sorted([e for e in pipeline if e['book'] == book],
                       key=lambda e: e.get('chapter_number') or 0)
    prev_e = next((e for e in same_book if e['chapter_number'] == n - 1), None)
    next_e = next((e for e in same_book if e['chapter_number'] == n + 1), None)
    return prev_e, next_e


def escape_prose_char(text):
    """Escape <, >, & but not quotes or apostrophes."""
    return _html.escape(text, quote=False)


def prose_to_html(prose):
    """Convert plain prose to HTML <p> tags, preserving single-newline line breaks for dialogue."""
    import re
    paras = [p.strip() for p in prose.strip().split('\n\n') if p.strip()]
    result = []
    for p in paras:
        # Drop standalone markdown bold/italic title lines (e.g. **Glass Hearts**)
        # — the chapter title is already rendered in the <h1> above the article.
        if re.match(r'^\*{1,3}.+\*{1,3}$', p):
            continue
        # Escape HTML chars first, then convert single newlines → <br> for dialogue lines
        escaped = escape_prose_char(p)
        escaped = escaped.replace('\n', '<br>\n      ')
        result.append(f'      <p>{escaped}</p>')
    return '\n'.join(result)


def render_chapter_html(entry, prev_entry, next_entry):
    """Generate a full static HTML page for a chapter, matching the existing site format."""
    assets = entry.get('assets', {})
    meta   = derive_chapter_meta(entry)
    series = meta['series']
    n      = entry['chapter_number']
    title  = entry['chapter']

    chapter_id        = meta['chapter_id']
    chapter_slug      = meta['chapter_slug']
    image_name        = meta['image_name']
    series_url        = series['series_url']
    series_name       = series['name']
    genre             = series['genre']
    blurb             = assets.get('blurb', '')
    tagline           = assets.get('tagline', '')
    author_note       = (assets.get('author_note') or '').strip()
    prose             = assets.get('prose', '')
    header_image_path = assets.get('header_image_path')

    prose_html      = prose_to_html(prose)
    title_esc       = _html.escape(title)
    series_name_esc = _html.escape(series_name)
    tagline_esc     = escape_prose_char(tagline)
    blurb_esc       = escape_prose_char(blurb)

    # JSON-LD (built as a dict so curly braces are safe)
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type":    "Chapter",
        "name":     f"Chapter {n} \u2014 {title}",
        "url":      f"https://realmsandroads.com/chapters/{chapter_slug}.html",
        "author":   {"@type": "Person", "name": "Fidel Namisi"},
        "isPartOf": {"@type": "Book", "name": series_name,
                     "url": f"https://realmsandroads.com{series_url}"},
        "genre":      genre,
        "inLanguage": "en",
        "isAccessibleForFree": True,
    }, indent=2)

    # Header image block
    if header_image_path:
        header_image_block = (
            f'    <div style="width:100%;max-height:420px;overflow:hidden;line-height:0;">\n'
            f'      <img src="/img/{image_name}" alt="Chapter {n} \u2014 {title_esc}"'
            f' style="width:100%;max-height:420px;object-fit:cover;object-position:center 30%;display:block;">\n'
            f'    </div>\n\n'
        )
    else:
        header_image_block = ''

    # Audio player block — guard against legacy dict format
    _audio_raw = assets.get('audio', '')
    audio_url  = (_audio_raw if isinstance(_audio_raw, str) else (_audio_raw or {}).get('s3_url', '') or '').strip()
    if audio_url:
        audio_block = (
            '    <div class="chapter-audio" aria-label="Listen to this chapter">\n'
            '      <div class="chapter-audio-label">🎧 Listen to this chapter</div>\n'
            f'      <audio controls preload="none" style="width:100%;">\n'
            f'        <source src="{_html.escape(audio_url)}" type="audio/mpeg">\n'
            '        Your browser does not support audio playback.\n'
            '      </audio>\n'
            '    </div>\n\n'
        )
    else:
        audio_block = ''

    # Author note block
    if author_note:
        author_note_block = (
            '    <aside class="author-note" aria-label="Author note">\n'
            '      <div class="author-note-label">Author&rsquo;s Note</div>\n'
            f'      <p>{escape_prose_char(author_note)}</p>\n'
            '    </aside>\n\n'
        )
    else:
        author_note_block = ''

    # Prev/next nav links
    if prev_entry:
        prev_meta  = derive_chapter_meta(prev_entry)
        prev_slug  = prev_meta['chapter_slug']
        prev_n     = prev_entry['chapter_number']
        prev_title = _html.escape(prev_entry['chapter'])
        nav_prev   = f'<a href="/chapters/{prev_slug}.html" class="nav-prev">Ch.{prev_n} &mdash; {prev_title} &larr;</a>'
    else:
        nav_prev = ('<span style="font-family:var(--font-ui);font-size:0.75rem;'
                    'color:var(--text-muted-dark);">&#8592; Beginning of Series</span>')

    nav_next = ''
    if next_entry:
        next_meta  = derive_chapter_meta(next_entry)
        next_slug  = next_meta['chapter_slug']
        next_n     = next_entry['chapter_number']
        next_title = _html.escape(next_entry['chapter'])
        nav_next   = f'<a href="/chapters/{next_slug}.html" class="nav-next">Ch.{next_n} &mdash; {next_title} &rarr;</a>'

    nav_block = f'''    <nav class="chapter-nav" aria-label="Chapter navigation &mdash; top">
      {nav_prev}
      <a href="{series_url}" class="nav-toc-center">Series Overview</a>
      {nav_next}
    </nav>'''

    nav_block_bottom = f'''    <nav class="chapter-nav" aria-label="Chapter navigation &mdash; bottom">
      {nav_prev}
      <a href="{series_url}" class="nav-toc-center">Series Overview</a>
      {nav_next}
    </nav>'''

    # Series label inline styles (matching existing pages exactly)
    series_label_styles = (
        'color:inherit;text-decoration:none;border-bottom:1px solid rgba(225,177,90,.35);'
        'transition:border-color .2s;'
    )
    series_label_hover  = "this.style.borderBottomColor='var(--ancestral-gold)'"
    series_label_out    = "this.style.borderBottomColor='rgba(225,177,90,.35)'"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chapter {n} &mdash; {title_esc} | {series_name_esc} \u2014 Realms and Roads</title>
  <meta name="description" content="Chapter {n} &mdash; {title_esc} \u2014 {series_name_esc}. A {genre} story by Fidel Namisi. Free to read online at Realms and Roads.">
  <link rel="canonical" href="https://realmsandroads.com/chapters/{chapter_slug}.html">


  <link rel="icon" href="/img/favicon.ico" type="image/x-icon">
  <link rel="stylesheet" href="/css/style.css">
  <!-- GA4 Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-ZCKFL71BXY"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-ZCKFL71BXY');</script>
  <link rel="alternate" type="application/rss+xml" title="Realms and Roads \u2014 New Chapters" href="/feed.xml">
  <meta property="og:image" content="https://realmsandroads.com/img/og-banner.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <script type="application/ld+json">
  {json_ld}
  </script>
</head>
<body class="chapter-page" data-chapter-id="{chapter_id}" data-chapter-slug="{chapter_slug}">
  <div id="reading-progress-bar" aria-hidden="true"></div>
  <a href="#main-content" class="skip-link">Skip to content</a>

  <nav class="site-nav" aria-label="Main navigation">
    <div class="nav-inner">
      <a href="/" class="nav-brand" aria-label="Realms and Roads">
        <img src="/img/logo25.jpg" alt="Realms and Roads logo" class="nav-logo-mark" style="height:44px;width:auto;border-radius:50%;object-fit:cover;">
        <div>
          <div class="nav-site-name">Realms &amp; Roads</div>
          <div class="nav-site-tagline">Many paths, endless stories</div>
        </div>
      </a>
      <ul class="nav-links" id="nav-links" role="list">
        <li><a href="/">Home</a></li>
        <li><a href="/table-of-contents.html" class="active">Stories</a></li>
        <li><a href="/listen.html">Listen</a></li>
        <li><a href="/start-here.html">New Readers</a></li>
        <li><a href="/search.html">Search</a></li>
        <li><a href="/about.html">About</a></li>
        <li><a href="/support.html">Support</a></li>
        <li class="nav-cta"><a href="/subscribe.html">Join</a></li>
      </ul>
      <div class="nav-controls">
        <button id="theme-toggle" class="btn-icon" aria-label="Toggle dark/light mode">&#127769;</button>
        <button class="nav-hamburger" aria-label="Open navigation menu" aria-expanded="false" aria-controls="nav-links">
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
  </nav>

  <main id="main-content" class="site-main" data-chapter-id="{chapter_id}">

{header_image_block}    <header class="chapter-header">
      <div class="chapter-series-label"><a href="{series_url}" style="{series_label_styles}" onmouseover="{series_label_hover}" onmouseout="{series_label_out}">{series_name_esc}</a> &nbsp;&middot;&nbsp; {genre}</div>
      <h1 class="chapter-title-main">Chapter {n} &mdash; {title_esc}</h1>
      <div class="chapter-meta-bar">
        <span>By Fidel Namisi</span>
        <span class="sep">&middot;</span>
        <span>2026</span>
        <span class="sep">&middot;</span>
        <span id="reading-time">Loading&hellip;</span>
      </div>
    </header>

    <div class="chapter-toolbar">
      <div class="chapter-toolbar-group">
        <span class="chapter-toolbar-label">Text size</span>
        <div class="font-controls" aria-label="Font size controls">
          <button class="font-size-btn" data-size="sm" aria-label="Small text">A</button>
          <button class="font-size-btn active" data-size="md" aria-label="Medium text">A</button>
          <button class="font-size-btn" data-size="lg" aria-label="Large text">A</button>
          <button class="font-size-btn" data-size="xl" aria-label="Extra large text">A</button>
        </div>
      </div>
      <div class="chapter-toolbar-group">
        <button class="bookmark-btn" aria-pressed="false" aria-label="Bookmark this chapter">&#9825; Save</button>
        <button class="share-btn" data-share="copy" aria-label="Copy link">&#8856; Copy Link</button>
        <button class="share-btn" data-share="twitter" aria-label="Share on X / Twitter">&#120143; Share</button>
        <button class="share-btn" data-share="whatsapp" aria-label="Share on WhatsApp">&#128172; WhatsApp</button>
      </div>
    </div>

{nav_block}

    <div class="chapter-blurb-block" style="max-width:680px;margin:2rem auto;padding:0 1.5rem;">
      <p style="font-family:var(--font-heading);font-style:italic;font-size:1.05rem;color:var(--ancestral-gold);margin-bottom:0.75rem;">{tagline_esc}</p>
      <p style="font-family:var(--font-body);font-size:0.95rem;color:var(--text-muted-dark);line-height:1.7;">{blurb_esc}</p>
    </div>

{audio_block}{author_note_block}    <article class="chapter-content" aria-label="Chapter text">
{prose_html}
    </article>

    <div class="reactions-bar" aria-label="Reactions">
      <span class="reactions-label">React</span>
      <button class="reaction-btn" data-emoji="fire" aria-label="Fire reaction"><span class="emoji">&#128293;</span><span class="reaction-count">0</span></button>
      <button class="reaction-btn" data-emoji="heart" aria-label="Heart reaction"><span class="emoji">&#10084;</span><span class="reaction-count">0</span></button>
      <button class="reaction-btn" data-emoji="cry" aria-label="Emotional reaction"><span class="emoji">&#128557;</span><span class="reaction-count">0</span></button>
      <button class="reaction-btn" data-emoji="mind" aria-label="Mind blown reaction"><span class="emoji">&#129327;</span><span class="reaction-count">0</span></button>
      <button class="reaction-btn" data-emoji="clap" aria-label="Applause reaction"><span class="emoji">&#128079;</span><span class="reaction-count">0</span></button>
    </div>

    <div class="support-callout">
      <h3>Enjoying the story?</h3>
      <p>Support the creation of more stories &mdash; become a member and get early access to new chapters.</p>
      <a href="/subscribe.html" class="btn btn-primary">Join Today &rsaquo;</a>
    </div>

{nav_block_bottom}


    <div class="comments-section">
      <h2 class="comments-heading">Join the Conversation</h2>
      <p style="color:var(--text-muted-dark);line-height:1.8;margin-bottom:1.5rem;">Thoughts on this chapter? Head over to Substack to leave a comment, reply to other readers, and follow along as the story unfolds.</p>
      <a href="https://realmsandroads.substack.com/" target="_blank" rel="noopener" class="btn btn-primary">Discuss on Substack &#8599;</a>
    </div>

  </main>

  <footer class="site-footer" role="contentinfo">
    <div class="footer-inner">
      <div>
        <span class="footer-brand-name">Realms &amp; Roads</span>
        <p class="footer-brand-desc">Many roads. Endless worlds. Start anywhere.</p>
        <div class="footer-social">
          <a href="https://www.patreon.com/c/realmsandroads" target="_blank" rel="noopener" class="social-link">Patreon</a>
        </div>
      </div>
      <div>
        <div class="footer-col-heading">Stories</div>
        <ul class="footer-links">
          <li><a href="/series/outlaws-and-outcasts.html">Outlaws and Outcasts</a></li>
          <li><a href="/series/rise-of-the-rain-queen.html">Rise of the Rain Queen</a></li>
          <li><a href="/series/man-of-stone-and-shadow.html">Man of Stone and Shadow</a></li>
          <li><a href="/table-of-contents.html">All Chapters</a></li>
        </ul>
      </div>
      <div>
        <div class="footer-col-heading">Navigate</div>
        <ul class="footer-links">
          <li><a href="/">Home</a></li>
          <li><a href="/start-here.html">New Readers</a></li>
          <li><a href="/search.html">Search</a></li>
          <li><a href="/about.html">About Fidel Namisi</a></li>
          <li><a href="/support.html">Support</a></li>
          <li><a href="https://www.patreon.com/c/realmsandroads" target="_blank" rel="noopener">Patreon</a></li>
                  <li><a href="/contact.html">Contact</a></li>
          <li><a href="/terms.html">Terms &amp; Conditions</a></li>
          <li><a href="/privacy.html">Privacy Policy</a></li>
          <li><a href="/refund.html">Refund Policy</a></li>
</ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>&copy; 2026 Realms and Roads. All rights reserved. Written by Fidel Namisi.</p>
      <p>Hosted on <a href="https://firebase.google.com" target="_blank" rel="noopener">Firebase</a>.</p>
    </div>
  </footer>

  <script src="/js/main.js"></script>

  <script src="/js/rr-auth.js"></script>
  <script src="/js/chapter-gate.js"></script>
</body>
</html>'''


def render_series_html(series, first_chapter_entry=None):
    """
    Generate a full static HTML page for a series landing page.
    The chapter list is DATA-DRIVEN via JS fetching /data/chapters.json.

    series: dict with keys name, slug, abbrev, genre, series_url, img_prefix,
            synopsis (optional), tagline (optional).
    first_chapter_entry: a content pipeline entry (may be None).
    """
    import html as _h

    name     = series['name']
    slug     = series['slug']
    abbrev   = series['abbrev']
    genre    = series['genre']
    synopsis = series.get('synopsis', '')
    tagline  = series.get('tagline', '')

    name_esc     = _h.escape(name)
    genre_esc    = _h.escape(genre)
    synopsis_esc = _h.escape(synopsis, quote=False)
    tagline_esc  = _h.escape(tagline, quote=False)

    start_url    = f'/chapters/{slug}-chapter-1.html'
    cover_img    = f'/img/{abbrev}-ch1-header.jpg'
    canonical    = f'https://realmsandroads.com/series/{slug}.html'

    # JS uses the series name directly (baked into the page)
    series_name_js = name.replace("'", "\\'")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name_esc} &mdash; Realms and Roads</title>
  <meta name="description" content="{synopsis_esc} Free to read online at Realms and Roads.">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="/img/favicon.ico" type="image/x-icon">
  <link rel="stylesheet" href="/css/style.css">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-ZCKFL71BXY"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-ZCKFL71BXY');</script>
  <link rel="alternate" type="application/rss+xml" title="Realms and Roads &mdash; New Chapters" href="/feed.xml">
  <meta property="og:image" content="https://realmsandroads.com/img/og-banner.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
</head>
<body>
  <div id="reading-progress-bar" aria-hidden="true"></div>
  <a href="#main-content" class="skip-link">Skip to content</a>

  <nav class="site-nav" aria-label="Main navigation">
    <div class="nav-inner">
      <a href="/" class="nav-brand" aria-label="Realms and Roads">
        <img src="/img/logo25.jpg" alt="Realms and Roads logo" class="nav-logo-mark" style="height:44px;width:auto;border-radius:50%;object-fit:cover;">
        <div>
          <div class="nav-site-name">Realms &amp; Roads</div>
          <div class="nav-site-tagline">Many paths, endless stories</div>
        </div>
      </a>
      <ul class="nav-links" id="nav-links" role="list">
        <li><a href="/">Home</a></li>
        <li><a href="/table-of-contents.html" class="active">Stories</a></li>
        <li><a href="/listen.html">Listen</a></li>
        <li><a href="/start-here.html">New Readers</a></li>
        <li><a href="/search.html">Search</a></li>
        <li><a href="/about.html">About</a></li>
        <li><a href="/support.html">Support</a></li>
        <li class="nav-cta"><a href="/subscribe.html">Join</a></li>
      </ul>
      <div class="nav-controls">
        <button id="theme-toggle" class="btn-icon" aria-label="Toggle dark/light mode">&#127769;</button>
        <button class="nav-hamburger" aria-label="Open navigation menu" aria-expanded="false" aria-controls="nav-links">
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
  </nav>

  <header class="series-hero">
    <div class="series-hero-inner">
      <div class="series-cover-frame">
        <img src="{cover_img}" alt="{name_esc} &mdash; series cover" style="width:100%;display:block;border-radius:6px;">
      </div>
      <div>
        <div class="series-detail-genre">{genre_esc} &nbsp;&middot;&nbsp; Realms and Roads</div>
        <h1 class="series-detail-title">{name_esc}</h1>
        <div style="font-family:var(--font-body);font-style:italic;font-size:1.15rem;color:var(--ancestral-gold);margin-bottom:1.5rem;opacity:0.85;">{tagline_esc}</div>
        <div class="series-detail-synopsis">
          <p>{synopsis_esc}</p>
        </div>
        <div class="series-detail-ctas">
          <a href="{start_url}" class="btn btn-primary">Start Reading &rsaquo;</a>
          <a href="/table-of-contents.html" class="btn btn-ghost">All Stories</a>
        </div>
      </div>
    </div>
  </header>

  <main id="main-content" class="site-main">
    <section style="margin-bottom:3rem;">
      <div class="section-eyebrow" style="margin-bottom:0.75rem;">Chapters</div>
      <h2 style="font-family:var(--font-heading);font-size:1.4rem;color:var(--text-on-dark);margin-bottom:0.5rem;font-weight:600;">Available Now</h2>
      <p id="series-chapter-count" style="font-family:var(--font-ui);font-size:0.8rem;color:var(--text-muted-dark);margin-bottom:1.5rem;"></p>
      <ol class="chapter-list" id="series-chapter-list" style="max-width:700px;" aria-label="{name_esc} chapters">
        <li style="font-family:var(--font-ui);font-size:0.85rem;color:var(--text-muted-dark);padding:1rem 0;">Loading chapters&hellip;</li>
      </ol>
    </section>

    <div class="support-callout" style="max-width:700px;">
      <h3>Get Early Access</h3>
      <p>Become a member to read upcoming chapters before they go public &mdash; and help keep these stories growing.</p>
      <a href="/subscribe.html" class="btn btn-primary">Join Today &rsaquo;</a>
    </div>
  </main>

  <footer class="site-footer" role="contentinfo">
    <div class="footer-inner">
      <div>
        <span class="footer-brand-name">Realms &amp; Roads</span>
        <p class="footer-brand-desc">Many roads. Endless worlds. Start anywhere.</p>
        <div class="footer-social">
          <a href="https://www.patreon.com/c/realmsandroads" target="_blank" rel="noopener" class="social-link">Patreon</a>
        </div>
      </div>
      <div>
        <div class="footer-col-heading">Stories</div>
        <ul class="footer-links">
          <li><a href="/series/outlaws-and-outcasts.html">Outlaws and Outcasts</a></li>
          <li><a href="/series/rise-of-the-rain-queen.html">Rise of the Rain Queen</a></li>
          <li><a href="/series/man-of-stone-and-shadow.html">Man of Stone and Shadow</a></li>
          <li><a href="/series/love-back.html">Love Back</a></li>
          <li><a href="/series/short-and-sweet.html">Short and Sweet</a></li>
          <li><a href="/table-of-contents.html">All Chapters</a></li>
        </ul>
      </div>
      <div>
        <div class="footer-col-heading">Navigate</div>
        <ul class="footer-links">
          <li><a href="/">Home</a></li>
          <li><a href="/start-here.html">New Readers</a></li>
          <li><a href="/search.html">Search</a></li>
          <li><a href="/about.html">About Fidel Namisi</a></li>
          <li><a href="/support.html">Support</a></li>
          <li><a href="/contact.html">Contact</a></li>
          <li><a href="/terms.html">Terms &amp; Conditions</a></li>
          <li><a href="/privacy.html">Privacy Policy</a></li>
          <li><a href="/refund.html">Refund Policy</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>&copy; 2026 Realms and Roads. All rights reserved. Written by Fidel Namisi.</p>
      <p>Hosted on <a href="https://firebase.google.com" target="_blank" rel="noopener">Firebase</a>.</p>
    </div>
  </footer>

  <script src="/js/main.js"></script>
  <script src="/js/rr-auth.js"></script>
  <script src="/js/auth-state.js"></script>
  <script src="/js/header-nav.js"></script>
  <script>
  (function() {{
    var SERIES_NAME = '{series_name_js}';
    fetch('/data/chapters.json')
      .then(function(r) {{ return r.json(); }})
      .then(function(chapters) {{
        var filtered = chapters.filter(function(c) {{ return c.series === SERIES_NAME; }});
        var list = document.getElementById('series-chapter-list');
        var countEl = document.getElementById('series-chapter-count');
        if (!filtered.length) {{
          list.innerHTML = '<li style="font-family:var(--font-ui);font-size:0.85rem;color:var(--text-muted-dark);padding:1rem 0;">Coming soon</li>';
          return;
        }}
        countEl.textContent = filtered.length + ' chapter' + (filtered.length === 1 ? '' : 's') + ' available';
        var html = '';
        filtered.forEach(function(c, i) {{
          var num = c.chapter ? c.chapter.replace('Chapter ', '') : String(i + 1);
          var title = c.title || c.chapter || ('Chapter ' + (i + 1));
          var url = c.url || '#';
          html += '<li class="chapter-list-item"><a href="' + url + '" rel="chapter">';
          html += '<span class="ch-num">Ch. ' + num + '</span>';
          html += '<span class="ch-title">' + title + '</span>';
          html += '<span class="ch-meta">2026 &middot; Free</span>';
          html += '</a></li>';
        }});
        list.innerHTML = html;
      }})
      .catch(function() {{
        var list = document.getElementById('series-chapter-list');
        list.innerHTML = '<li style="font-family:var(--font-ui);font-size:0.85rem;color:var(--text-muted-dark);padding:1rem 0;">Coming soon</li>';
      }});
  }})();
  </script>
</body>
</html>'''
