# RUNBOOK.md

Domains, DNS, and hosting for **bryansebesta.net**.

`PRODUCT.md` covers what is being built and why; `CLAUDE.md` covers how to work
in this repo. This file covers the infrastructure underneath both — the parts
that live in vendor dashboards rather than in git, and are therefore the
easiest to forget and the hardest to reconstruct.

Established 2026-07-21.

## 1. Current topology

```
Network Solutions          Netlify DNS              Netlify
(registrar only)     →     (dns1-4.p03.nsone.net)   →   site: bryansebestanet
                                                        repo: bsebesta/bryan2026blog
                                                        branch: main
```

| Thing | Value |
|---|---|
| Registrar | Network Solutions (formerly Domain.com). Renews 2027-01-30, auto-renew on |
| DNS | **Netlify DNS** since 2026-07-21 — `dns1.p03.nsone.net` … `dns4.p03.nsone.net` |
| Apex | `bryansebesta.net` → Netlify (`52.52.192.191`, `13.52.188.95`) |
| `www` | redirects to apex (Netlify handles this once apex is primary) |
| `micro` | CNAME → `bsebesta.micro.blog` — the Micro.blog subdomain (§3) |
| Build | `netlify.toml` — `hugo` → `public`, `HUGO_VERSION = "0.158.0"` |
| `baseURL` | `https://bryansebesta.net/` in `hugo.toml` |
| DNSSEC | **disabled** — keep it that way (§4) |

**The registrar holds registration only.** Nothing in Network Solutions' DNS
panel is consulted any more; delegation happens above the zone, so once the NS
records point at NS1, the old zone is a historical artifact. Do not spend time
tidying it.

## 2. Two settings that must agree

| Setting | Where | What it does | When |
|---|---|---|---|
| `baseURL` | `hugo.toml` | Written into canonical tags, feed item URLs, `sitemap.xml` | Build time |
| Primary domain | Netlify → Domain management | What the edge redirects *to* | Request time |

They are independent and can silently disagree. If `baseURL` is the apex while
Netlify's primary is `www`, the site works — but every visitor takes an extra
redirect hop and the feed advertises URLs that aren't where readers land.

**Both are the apex.** Change one, change the other.

This matters more than it looks because of §12.3: the site's RSS feed is
intended as a Micro.blog Source, which pushes those URLs into the fediverse and
into other servers' caches. Wrong URLs there are effectively permanent.

## 3. The Micro.blog subdomain — `micro.bryansebesta.net`

Set up 2026-07-21. The blog is the pre-existing `bsebesta.micro.blog` account
(username `bsebesta`), custom-mapped to `micro.bryansebesta.net`. Recorded here
as the reference procedure; must complete **before** backfilling microposts,
because PRODUCT.md §12.3 keys ingest on final `url:` values.

**A subdomain needs one CNAME — not the A record.** Micro.blog's instructions
list an A record → `104.200.22.214`; that is for root-domain mappings only.
The apex here lives on Netlify, so the A record must never be added.

The record, in Netlify DNS:

| Type | Name | Value | TTL |
|---|---|---|---|
| CNAME | `micro` | `bsebesta.micro.blog` | 3600 |

The value is `<username>.micro.blog` and must match the username of the blog
the domain is mapped to. Confirm the username in Micro.blog rather than
assuming it from an old URL.

Sequence:

1. Add the CNAME above in Netlify DNS.
2. Micro.blog → Design → Blog Settings → **Domain name** → `micro.bryansebesta.net`
   → Update Settings.
3. Wait. Micro.blog provisions HTTPS automatically; a CNAME propagates in
   minutes, faster than the §2 nameserver change did.
4. **The real gate is the feed's *internal* URLs, not just that it answers.**
   After a domain change Micro.blog rewrites item URLs to the new domain, but
   not instantly. Ingesting during that window freezes `bsebesta.micro.blog`
   into every file. Wait until:

   ```bash
   curl -s https://micro.bryansebesta.net/feed.json | grep '"url"' | head
   ```

   shows `micro.bryansebesta.net`, **not** `bsebesta.micro.blog`. Checking that
   the domain merely resolves is not sufficient — observed 2026-07-21, the feed
   answered at the new domain for several minutes while every item `url` and the
   `home_page_url` still carried the old one.
5. Run `make micro-api` (or `make micro`).

**Note (2026-07-21):** the ingest now *owns the domain* — `micro.py` keeps only
the URL path and prepends `micro.bryansebesta.net`, so a stale
`bsebesta.micro.blog` can no longer freeze into the vault regardless of what the
feed or API reports. (The Micropub API in fact still returns the old domain for
pre-migration posts.) So the gate in step 4 is now a nicety, not a hard
requirement — it only matters that the post is actually *served* at the new
domain so the published link works for readers.

**Unverified:** whether `bsebesta.micro.blog` continues to redirect after the
custom domain is set. Micro.blog promises URL durability when *migrating away*
from the platform, which is not the same claim. Ask before relying on it.

### 3.1 App token for API ingest

The incremental path (`make micro-api`, and the Import Microposts dock droplet)
pulls live from the Micropub API and needs an app token.

1. Micro.blog → **Account → App tokens** → generate one.
2. Add to the shell profile so terminals — including the dock droplet's —
   inherit it:

   ```bash
   # ~/.zshrc
   export MICROBLOG_TOKEN=your-token-here
   ```

3. Open a new terminal (or re-run the droplet) so it's picked up.

The token lives **only** in the environment. It is never committed; `.gitignore`
also blocks `.env` / `*.token` as a backstop. The variable name is configurable
(`micro.token_env` in `pipeline/config.yaml`). Verify with a dry run:
`make micro-api` — it should list posts without writing anything.

## 4. Gotchas, each of which cost a debugging round

**Network Solutions' "connected services" override the zone.** A domain with a
Hosting service attached answers on 443 from their under-construction host —
which has no certificate for your domain, producing `ERR_SSL_PROTOCOL_ERROR`
rather than an honest DNS failure. The service also answers for unmatched
subdomains, which looks exactly like a wildcard record that isn't there. The
records panel and the live answers can differ while a service is attached.
**Disconnect the service before trusting anything the DNS panel shows.**

**"Custom Nameservers" is not how you change nameservers.** That page registers
glue records for nameservers *you operate*, which is why it demands an IP
address. Entering one there for a host you don't control is wrong. Delegation
lives at **Domain → Advanced Tools → Nameservers (DNS) → Manage**, which takes
four hostnames and no IPs.

**DNSSEC must be off before changing nameservers.** If enabled, the registry
keeps publishing signatures the new nameservers cannot produce, and validating
resolvers stop answering entirely — a harder outage than a misconfigured
record, because it fails closed at the resolver. Currently disabled; verify
before any future nameserver change.

**Certificates follow delegation, not the other way round.** Let's Encrypt
validates over the public path, so a TLS warning while NS records are still
propagating is sequence, not fault. Delegation TTLs for `.net` can be long;
minutes to hours is normal, 48 hours is the documented ceiling.

**Every dashboard reads a cached view of DNS. Verify against the registry
instead.** Delegation records for `.net` carry a **172800-second (48 hour)**
TTL, so any resolver that cached the old nameservers before a change can hold
them for two days. This produces a period where the configuration is provably
correct and three separate systems all report failure:

- Netlify's certificate check fails with *"&lt;domain&gt; doesn't appear to be
  served by Netlify"* — its resolver is stale, not your DNS.
- The site still serves the registrar's parking page for some visitors.
- Local `dig` disagrees with `dig @8.8.8.8`.

The authoritative check bypasses every cache by asking the TLD servers what
delegation the *registry* publishes:

```bash
dig NS bryansebesta.net @a.gtld-servers.net +norecurse
```

**If that returns the right nameservers, the configuration is correct and the
only correct action is to wait.** Do not "fix" anything in response to a
dashboard during this window — that is how a working setup gets broken.

**Incognito does not clear DNS.** A private window bypasses HTTP cache,
cookies, and stored 301s, but name resolution happens below the browser. To
actually refresh:

```bash
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder   # macOS
```

Chrome keeps its own at `chrome://net-internals/#dns` → Clear host cache. If
the stale entry lives at the ISP's resolver, none of this helps — point the
machine at `1.1.1.1` temporarily to see through it.

**Netlify can skip the build entirely.** A deploy reporting *"All files already
uploaded by a previous deploy with the same commits"* and finishing in seconds
did **not** run Hugo; it reused artifacts from an earlier deploy of that
commit. If site configuration changed since — primary domain, environment —
the reused output still reflects the old settings. Symptom: emitted links carry
the wrong hostname despite a correct `baseURL` in `hugo.toml`. Fix with
**Deploys → Trigger deploy → Deploy without cache**, then confirm the emitted
URLs rather than trusting a green deploy.

**The upsell cart sits in the flow.** Network Solutions' domain page puts
pre-checked additional domains and pre-checked privacy add-ons directly above
the Advanced Tools section. Scroll past deliberately.

## 5. Verification

Run these rather than trusting a dashboard — a green badge in Netlify confirms
Netlify's own configuration and says nothing about where the internet is sent.

```bash
# THE AUTHORITATIVE CHECK — what the registry publishes, above every cache.
# Start here when anything disagrees. If this is right, nothing is broken.
dig NS bryansebesta.net @a.gtld-servers.net +norecurse

# Who owns the zone — should be nsone.net with a netlify.com contact
dig +short SOA bryansebesta.net @8.8.8.8

# Delegation — should list the four nsone.net hosts
dig +short NS bryansebesta.net

# Apex and www — should be Netlify's, not a registrar parking IP
dig +short A bryansebesta.net
dig +short www.bryansebesta.net

# Bypass propagation: ask the new nameserver directly.
# Confirms the zone is correct even while delegation is still stale.
dig +short A bryansebesta.net @dns1.p03.nsone.net

# Micro.blog subdomain — should CNAME to bsebesta.micro.blog
dig +short micro.bryansebesta.net

# Mail — currently empty by design; if this ever returns records,
# they must be carried across before any nameserver change
dig +short MX bryansebesta.net

# Emitted URLs — the real test after a deploy. Should be bryansebesta.net,
# never *.netlify.app. These are what the RSS feed carries into the fediverse.
curl -s https://bryansebesta.net/ | grep -o 'https://[^"]*netlify.app[^"]*' | head
```

**Known-bad values**, useful for recognising a regression:

| Value | Meaning |
|---|---|
| `208.91.197.27` | Network Solutions under-construction page |
| `104.200.22.214` | Network Solutions parking / forwarding host |
| `ns1.domain.com`, `ns2.domain.com` | delegation reverted to the registrar |
| `bsebesta.micro.blog` on `www` | stale record from the 2023–24 Micro.blog setup |

## 6. History

- **2026-07-21** — Repo relinked to `bsebesta/bryan2026blog`. Hosting service
  disconnected at the registrar; DNS moved to Netlify DNS; `baseURL` changed
  from `bryan2026blog.netlify.app` to `bryansebesta.net`; apex set as Netlify's
  primary domain. Prior state: apex and `www` served the registrar's
  under-construction page, `www` additionally carried a stale CNAME to
  `bsebesta.micro.blog`, and eleven A records pointed at Network Solutions
  hosting and mail hosts that were never in use.

  Registry delegation confirmed correct the same afternoon. Certificate
  provisioning still failing at that point **on stale cache alone** — Netlify's
  check, the local resolver, and the browser were each reading a pre-change
  view while `@8.8.8.8` and `@1.1.1.1` already had the new delegation. Left to
  expire rather than "fixed." **This is the failure mode §4 exists to
  document:** on the day, three systems reported a broken configuration that
  was demonstrably correct.
