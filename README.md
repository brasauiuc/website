# BRASA at UIUC website

This is the website of the Brazilian Student Association chapter at the University of Illinois Urbana-Champaign. It's in English and Portuguese, and you don't need to be a developer to maintain it. Most changes can be made in the browser in a couple of minutes.

## The basics

To change anything, open the file on github.com, click the pencil icon, make your edit, and click "Commit changes" to save to `main`. The site rebuilds and goes live by itself about two minutes later. You can watch progress in the repository's Actions tab, where a green check means it's live.

If you break something, the old site stays up, because a failed build never replaces it. The Actions tab shows the error in plain words. To undo a change, open the file's History on github.com, copy the old text back, and commit.

Here is where things live:

| What | Where |
| --- | --- |
| Events and board members | The [Website Data Google Sheet](https://docs.google.com/spreadsheets/d/1qxJdhrN59IcJeYRflSpPxivYRztom4ReyoHbCc2xX64) |
| Event and board photos | `src/assets/events/` and `src/assets/board/` |
| Links, emails, domain | `src/site.toml` |
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

### Add or change events and board members

Both live in the [Website Data Google Sheet](https://docs.google.com/spreadsheets/d/1qxJdhrN59IcJeYRflSpPxivYRztom4ReyoHbCc2xX64), one tab each. Edit a row and the site updates by itself overnight, shortly after midnight in Champaign. To publish sooner, open the repository's Actions tab, choose "Deploy site", and click "Run workflow".

A row only appears on the site if its `include` box is checked, so you can prepare a row in advance or hide one without deleting it. Don't rename the columns or tabs, because the build reads them by name.

Everything in this file is public, so never put form responses, phone numbers, or member data in it. Anyone who can edit it can change the live site, so keep the editor list short.

| Events column | Notes |
| --- | --- |
| `date` | Required, written like `2026-09-25` |
| `start_time`, `end_time` | Optional, written like `8:00 PM` |
| `title` | Required, the same in both languages |
| `description_pt`, `description_en` | Fill in both, or leave both empty |
| `location` | Optional, the same in both languages |
| `rsvp_url` | Optional, must start with `https://`, and hidden once the date has passed |
| `image_path` | Optional, for example `src/assets/events/pelada.jpg` |
| `instagram_link` | Optional, must start with `https://` |

| Board column | Notes |
| --- | --- |
| `order` | Position on the page, starting at 1 |
| `name` | Required |
| `role_pt`, `role_en` | Both required |
| `major` | Required, and stays in English on both versions of the site. For two majors, write `First, Second` and each goes on its own line |
| `class_year` | Optional, shown as "Class of 2029" in both languages |
| `image_path` | Optional, for example `src/assets/board/ana.jpg`. Without a photo, the card shows initials |

Events on or after today appear under "Upcoming events", soonest first. After their date passes they move to "Past events", where the 5 most recent are shown. To change that number, edit `PAST_EVENTS_SHOWN` in `build.py`. Older rows can stay in the sheet.

A sheet can't hold pictures, so upload each photo to the repository with Add file, then Upload files, in the folder its `image_path` names. Board photos should be square, about 400 by 400 pixels, and under 200 KB. Event images should be under 300 KB, and they're shown whole, never cropped. Remove a former member's photo when they leave.

If a row has a problem, like a badly written date or a photo that isn't uploaded, the build stops and names the tab and row. The current site stays up until it's fixed.


## Rules

- Never display member data on this site. That means no directory, no names beyond the board, and no phone numbers. All intros go through forms and are made manually by the board.
- The site keeps English and Portuguese completely separate, with English pages at standard URLs and Portuguese pages under /pt/. Each language has its own pages, navigation, and components, while the EN/PT button switches between matching pages. Event titles, locations, board majors, and “Class of” lines are translated, while proper names like BRASA at UIUC, Instagram, and SSN remain unchanged. The build checks for missing translated pages or content. Exceptions include external Google Forms, which retain their original language, and GitHub Pages’ shared English 404 page, which links to the Portuguese version.
