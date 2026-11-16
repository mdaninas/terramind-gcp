"""Shared local theme assets and accessible appearance controls."""

THEME_SCRIPT = '<script src="/assets/theme.js"></script>'
THEME_STYLESHEET = '<link rel="stylesheet" href="/assets/theme.css">'

BRAND_IMAGES = (
    '<img class="brand-light" src="/assets/terramind-logo.png" '
    'alt="Terramind" width="216" height="72">'
    '<img class="brand-dark" src="/assets/terramind-logo-dark.png" '
    'alt="Terramind" width="216" height="72">'
)

THEME_CONTROL = (
    '<label class="theme-control" title="Color theme">'
    '<svg class="theme-icon" viewBox="0 0 20 20" fill="none" '
    'aria-hidden="true" focusable="false">'
    '<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/>'
    '<path d="M10 3a7 7 0 0 1 0 14z" fill="currentColor"/></svg>'
    '<select class="theme-select" data-theme-select aria-label="Color theme" disabled>'
    '<option value="system">System</option><option value="light">Light</option>'
    '<option value="dark">Dark</option></select></label>'
)
