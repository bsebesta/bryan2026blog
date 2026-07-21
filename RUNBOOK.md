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

## 3. Adding a subdomain (the Micro.blog case)

Required **before** backfilling microposts — see PRODUCT.md §12.3, which
depends on ingested `url:` values being final.

1. Register the Micro.blog account and create the hosted blog.
2. In Micro.blog, set the custom domain to `social.bryansebesta.net`.
   **Copy the CNAME target Micro.blog displays** rather than assuming it — do
   not guess this value.
3. In **Netlify DNS**, add a CNAME record: `social` → that target.
4. Wait for Micro.blog to report the domain verified and its certificate
   issued.
5. Confirm the feed now serves the new domain:
   `curl -s https://social.bryansebesta.net/feed.json | head`
6. **Only then** run `make micro` / `micro-apply`.

Ingesting before step 5 freezes `bsebesta.micro.blog` URLs into vault
frontmatter, and recovering costs a rewrite pass over a mixed corpus.

**Unverified:** whether `bsebesta.micro.blog` continues to redirect after the
custom domain is set. Micro.blog promises URL durability when *migrating away*
from the platform, which is not the same claim. Ask before relying on it.

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

**The upsell cart sits in the flow.** Network Solutions' domain page puts
pre-checked additional domains and pre-checked privacy add-ons directly above
the Advanced Tools section. Scroll past deliberately.

## 5. Verification

Run these rather than trusting a dashboard — a green badge in Netlify confirms
Netlify's own configuration and says nothing about where the internet is sent.

```bash
# Delegation — should list the four nsone.net hosts
dig +short NS bryansebesta.net

# Apex and www — should be Netlify's, not a registrar parking IP
dig +short A bryansebesta.net
dig +short www.bryansebesta.net

# Bypass propagation: ask the new nameserver directly.
# Confirms the zone is correct even while delegation is still stale.
dig +short A bryansebesta.net @dns1.p03.nsone.net

# Subdomains
dig +short social.bryansebesta.net

# Mail — currently empty by design; if this ever returns records,
# they must be carried across before any nameserver change
dig +short MX bryansebesta.net
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
  from `bryan2026blog.netlify.app` to `bryansebesta.net`. Prior state: apex and
  `www` served the registrar's under-construction page, `www` additionally
  carried a stale CNAME to `bsebesta.micro.blog`, and eleven A records pointed
  at Network Solutions hosting and mail hosts that were never in use.
