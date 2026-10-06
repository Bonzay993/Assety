# Changelog

Notable changes to Assety are listed here so the local work can be reviewed
before it is pushed. The entries are grouped into independent change areas.

## Unreleased

### Brand identity

- Replaced the text-only wordmark on the landing page and workspace sidebar
  with a coordinated Assety wordmark and custom SVG inventory-box mark.
- Kept the mark vector-based so it stays crisp at responsive sizes.

### Landing page and pricing

- Added a Pricing navigation link that scrolls to a pricing section on the home
  page.
- Explained that this project has no paid plans or checkout, and linked visitors
  directly to account creation or sign in.
- Refreshed the landing-page hero, calls to action, feature cards, and spacing.
- Replaced the generic hero image with a labeled sample inventory preview and
  tightened the copy across the workflow, pricing, and use-case sections.
- Added restrained numbered steps, a consistent account call to action, and a
  cleaner footer; removed the hero entrance animation that clipped first paint.
- Reworked the public-page layout for phone, tablet, and desktop widths.
- Kept the shared footer at the viewport bottom on short pages, and confined
  landing-only styling to the home page.

### Application interface refresh

- Extended the landing page's typography, colour palette, cards, and button
  styling across account forms and signed-in inventory screens.
- Refined the workspace sidebar, active navigation, search header, dashboards,
  record lists, reports, settings, and forms for a more consistent interface.
- Added matching dark-mode surfaces and clearer mobile spacing for the refreshed
  application shell.
- Fixed the sidebar's desktop collapse animation, made the mobile menu use the
  full available width, and stopped the workspace shell from creating a
  page-wide horizontal scrollbar.
- Removed the collapsed sidebar monogram that overlapped its menu toggle, and
  kept the phone navigation hidden until the menu button is opened.

### Application reliability and security

- Isolated each user's company data, validated asset relationships, and corrected
  image upload and access checks.
- Added password verification before changing an account email and protected
  state-changing requests against cross-site request forgery.
- Hardened authentication, configuration, errors, logout, exports, and Heroku
  startup behavior.
- Preserved entered form data on validation errors and improved empty states,
  modal keyboard controls, and focus handling.

### Developer quality and documentation

- Added a local Windows launcher, repeatable tests, lint settings, and HTML/CSS
  validation helpers.
- Expanded regression coverage for authentication, company boundaries, assets,
  uploads, categories, locations, settings, exports, and landing-page pricing.
- Replaced the short README with a detailed application, architecture, routes,
  configuration, testing, deployment, security, and repository guide.
- Added an architecture illustration under `docs/images/` and linked the
  existing public-page artwork from the README.
- Added the local testing guide and cross-links to the changelog.

### Checks run

- Python integration suite: 50 tests passed against a disposable local MongoDB
  database.
- JavaScript suite: 20 tests passed in four suites.
- Ruff: all checks passed.
- Nu checker: 27 rendered HTML pages and both project stylesheets, with zero
  errors or warnings.
- Browser review: refreshed landing page at desktop and phone sizes; the Pricing
  navigation reached `#pricing`, and signup/sign-in destinations were present.
