# BRASA at UIUC website

This is the website of the Brazilian Student Association chapter at the University of Illinois Urbana-Champaign. It's in English and Portuguese, and you don't need to be a developer to maintain it. Most changes can be made in the browser in a couple of minutes.

## The basics

To change anything, open the file on github.com, click the pencil icon, make your edit, and click "Commit changes" to save to `main`. The site rebuilds and goes live by itself about two minutes later. You can watch progress in the repository's Actions tab, where a green check means it's live.

If you break something, the old site stays up, because a failed build never replaces it. The Actions tab shows the error in plain words. To undo a change, open the file's History on github.com, copy the old text back, and commit.

Here is where things live:

| What | Where |
| --- | --- |
| Links, emails, events, board members | `src/site.toml` |
| English pages | `src/index.html`, `src/prospective.html`, `src/alumni.html`, `src/board.html`, `src/contact.html`, `src/404.html` |
| Portuguese pages | The same file names inside `src/pt/` |
| Menu items | `src/partials/nav-links.html` and `src/partials/nav-links.pt-BR.html` |
| Header, footer, page head | `src/partials/` |
| Colors, fonts, spacing | `src/input.css` |
| Images and fonts | `src/assets/` |
| The build | `build.py` |
| Deployment | `.github/workflows/deploy.yml` |

`dist/` is the finished site. It's generated on every build and isn't stored in the repository, so never edit it.

## Common tasks

### Edit text on a page

Open the page in `src/` and change the words between the tags, leaving the tags themselves alone. Make the same change to its Portuguese twin in `src/pt/`. The comment at the very top of each page holds the title and description that appear in search results and link previews. Anything inside double curly braces, like `{{ALUMNI_FORM_URL}}`, is filled in automatically from `src/site.toml`.

Search the repository for `TODO` to find everything that still needs writing. On the live site, leftover TODOs appear in a dashed yellow box.

### Swap a form or social link

Open `src/site.toml` and replace the value under `[links]`, keeping the quotes. Every page updates. While a value is still `"TODO"`, its button does nothing and the build prints a warning.

| Setting | What it is | Where it shows up |
| --- | --- | --- |
| `INTRO_REQUEST_FORM_URL` | Prospective and admitted intro request Google Form | Prospective |
| `ALUMNI_FORM_URL` | Alumni Google Form | Alumni |
| `INSTAGRAM_URL` | Instagram profile | Contact, footer |
| `CONTACT_EMAIL` | Chapter email address, without `mailto:` | Contact, footer |
| `DOMAIN` | The real domain, replaces `DOMAIN_PLACEHOLDER` | Link previews, `CNAME` |

### Add or change a board member

Open `src/site.toml` and find the `[[board]]` blocks. Each block is one card, in the order written, so copy a block to add someone and delete a block to remove them.

```toml
[[board]]
name = "Full Name"
role = "President"
role_pt = "Presidente"
major = "Computer Science"
major_pt = "Ciência da Computação"
photo = "full-name.jpg"
linkedin = "https://www.linkedin.com/in/example"
```

`photo` and `linkedin` are optional, so delete those lines if unused. Without a photo the card shows initials. Photos go in `src/assets/board/` and should be square, about 400 by 400 pixels, and under 200 KB. Upload them on github.com with Add file, then Upload files. Remove a former member's photo when they leave.

### Add or remove an event

Open `src/site.toml` and edit the `[[events]]` blocks the same way. Remove events once they've passed, because the site doesn't do this for you. With no blocks left, the Home page says nothing is scheduled. Only `date` and `title` are required. Every field also needs a Portuguese version ending in `_pt`, such as `title_pt`.

### Answer the FAQ

FAQ answers are in `src/prospective.html` and `src/pt/prospective.html`. Check anything about university policy, costs, or visas against official sources and link to them, because these rules change.

### Swap the hero image

The Home page image is deliberately easy to replace, and its licensing and branding still need checking (see "Open items" below). Export your new image at widths of 640, 1024, 1600, and 2172 pixels in WebP format (the free site squoosh.app does this), and overwrite the files in `src/assets/hero/` using the same names. Then update both descriptions under `[hero]` in `src/site.toml`, and replace `src/assets/og-image.jpg` (1200 by 630 pixels), the picture used in link previews.

Pick a wide image, about three times as wide as it is tall, with the subject in the left half and a dark, calm right half. The text sits directly on the right side with no dark overlay, so it has to stay readable on its own. The only overlay is the short fade into the page along the bottom edge.

To remove the image entirely, delete the `img` tag from `src/partials/hero-image.html`. The hero falls back to a plain dark background.

### Add a page

Copy an existing page in `src/`, change the comment at the top, and add a link in `src/partials/nav-links.html`. Then do the same in Portuguese: create the page with the same file name in `src/pt/` and add a link in `src/partials/nav-links.pt-BR.html`. The build stops if either version is missing, because the language button would otherwise lead nowhere.

## Run the build on your own computer

This is optional, since github.com does it for you. You need Python 3.11 or newer from python.org and nothing else.

```sh
python3 build.py
python3 -m http.server 8000 -d dist
```

Then open http://localhost:8000. On Windows, use `py` instead of `python3`. The first build downloads the Tailwind program into `.tools/`, which is ignored by git.

## How deployment works

Every push to `main` runs `.github/workflows/deploy.yml` on GitHub's servers. It runs `build.py`, which fills the pages into `dist/` and compiles the CSS with Tailwind, then publishes `dist/` to GitHub Pages. The workflow can also be started by hand from the Actions tab with "Run workflow".

The site has no backend, database, analytics, cookies, or JavaScript. All data collection happens in external Google Forms.

To set up a new repository once, go to Settings, then Pages, and set Source to "GitHub Actions". Deploys fail until this is done.

## Point the custom domain at GitHub Pages

Do these steps in order, because adding the domain on GitHub before changing DNS protects it from being taken over by someone else.

1. In the GitHub organization's Settings, under Pages, add the domain and verify it with the TXT record GitHub gives you.
2. In the repository, go to Settings, then Pages. Under "Custom domain", type the domain and save.
3. At the domain registrar, create the DNS records below, and remove any older `A` or `CNAME` records for the same names.
4. In `src/site.toml`, set `DOMAIN` to the real domain.
5. Wait for DNS to spread, which can take up to a day. Then tick "Enforce HTTPS" in Settings, then Pages.
6. Start the workflow once more from the Actions tab, so link previews use the final `https` address.

| Type | Name | Value |
| --- | --- | --- |
| `A` | `@` | `185.199.108.153` |
| `A` | `@` | `185.199.109.153` |
| `A` | `@` | `185.199.110.153` |
| `A` | `@` | `185.199.111.153` |
| `AAAA` | `@` | `2606:50c0:8000::153` |
| `AAAA` | `@` | `2606:50c0:8001::153` |
| `AAAA` | `@` | `2606:50c0:8002::153` |
| `AAAA` | `@` | `2606:50c0:8003::153` |
| `CNAME` | `www` | `YOUR-GITHUB-ORG.github.io` |

These values come from GitHub's custom domain documentation, so check there if they ever stop working.

The domain setting that counts is the one in repository Settings. GitHub ignores `CNAME` files when a site is published through Actions. The `src/CNAME` file is kept, filled from `DOMAIN`, only so the repository records its domain and stays ready if the deploy method ever changes.

## Accounts and who owns what

Update this table at every board handoff. Record names only, and never put passwords here. Keep credentials in a password manager or another private place that the board controls, and make sure at least two people have access.

| Account | Used for | Name | Current owner |
| --- | --- | --- | --- |
| GitHub organization | Code and hosting | TODO | TODO |
| Domain registrar | The domain, renews yearly | TODO | TODO |
| Chapter Gmail | `CONTACT_EMAIL`, owns the Google Forms and their responses | TODO | TODO |

When the board changes, add the new people to the GitHub organization, transfer the registrar and Gmail access, and confirm the domain's renewal date and payment method. An expired domain is the most likely way for this site to go down.

## The privacy rule

Never display member data on this site. That means no directory, no names beyond the board, and no phone numbers. All intros go through forms and are made manually by the board.

## Why it's built this way

The goal is a site that still works in ten years with almost no attention, maintained by people who may never have coded.

Shared header and footer use a tiny build script rather than copies in each page. With six pages in two languages, a duplicated header means twelve edits for every menu change, and it's easy to miss one. A script also lets all links, events, and board members live in one file that's safe to edit, which duplication can't do. `build.py` is about 250 lines of standard Python with no packages to install, and Python comes preinstalled on GitHub's servers. Node isn't used at all, because the Tailwind standalone program doesn't need it.

Pages are plain HTML with a little Tailwind. Repeated pieces like `btn` and `eyebrow` are named classes in `src/input.css`, so one edit changes them everywhere.

The mobile menu and the FAQ accordion use the browser's built-in `details` element, and the language button is a plain link to the same page in the other language, so the site needs no JavaScript at all.

## The two languages

The rule is no mixing: English pages are entirely in English and Portuguese pages are entirely in Portuguese. Don't add Portuguese labels to English pages, or the reverse. Names like BRASA at UIUC, Instagram, and SSN stay as they are in both.

English lives at the normal addresses and Portuguese under `/pt/`, for example `/alumni.html` and `/pt/alumni.html`. Each language has its own pages in `src/` and `src/pt/`, and its own header, footer, menu, and board card in `src/partials/`, where the Portuguese files end in `.pt-BR.html`. The EN/PT button in the header goes to the same page in the other language, and all other links stay within the current language.

The build protects this rule in two ways. It stops if a page has no twin in the other language, and it stops if an event or board member is missing a Portuguese field in `src/site.toml`.

Two things can't follow the rule by themselves. Google Forms are outside this site, so they appear in whatever language they were written in. GitHub Pages also has only one error page for mistyped addresses, so a broken `/pt/` link lands on the English 404, where the PT button leads to the Portuguese one.

## Occasional maintenance

The Tailwind version is pinned in `build.py`, and its download is verified against `tailwind.sha256`. To upgrade, change `TAILWIND_VERSION` and replace that file with `sha256sums.txt` from the same Tailwind release. There's no need to upgrade unless something requires it.

The GitHub Actions in `deploy.yml` are pinned to exact versions. If deploys start failing with a message that an action is deprecated, update that action to its latest release, using the commit ID shown on its releases page.

Build errors explain what's wrong and where. The most common one is a missing quote in `src/site.toml`, and the error gives the line number.

## Open items

- The hero image shows the Alma Mater statue, including university marks. Check licensing and branding with the university before launch.
- The logo contains the Block I, a University of Illinois mark, so check that too. The current `src/assets/logo.png` is small, under 200 pixels wide, so ask for a vector version if one exists. If you replace it, also update `logo-120.png`, `favicon-32.png`, and `apple-touch-icon.png` in the same folder.

## Licenses

Fraunces and Manrope are used under the SIL Open Font License. Their license files are in `src/assets/fonts/`.
