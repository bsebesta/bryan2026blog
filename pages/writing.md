---
title: Writing
slug: writing
layout: hub
# Types this section gathers. `note` and `essay` are both writing; the essay
# is a form, not a subject (see config.yaml type_by_folder).
hub_types:
  - note
  - essay
# Show the Micro.blog stream on this hub, in its OWN area below the pages —
# hub.html renders an "Evergreen" list (notes + essays) and a separate
# "Microposts" list when this flag is set, never interleaved. Microposts aren't
# pages; they live in data/microposts.json as links out to Micro.blog
# (PRODUCT.md §4.2). Other hubs (Making, Library) leave this off, pages-only.
include_microposts: true
# Keep the hub out of content listings — it's navigation, not a note. It still
# builds and renders at /writing/; it just never appears in an index or feed.
build:
  list: never
---

Notes and essays, plus a stream of microposts.
