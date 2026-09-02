=== AI-Recommendable Connector ===
Contributors: ai-recommendable
Tags: schema, json-ld, ai discoverability, seo, structured data
Requires at least: 5.0
Tested up to: 6.4
Stable tag: 1.0.0
License: GPLv2 or later

Enables AI-Recommendable to deploy schema markup, content, and SEO improvements to your WordPress site.

== Description ==

This plugin connects your WordPress site to AI-Recommendable's discoverability platform. It allows:

* Automatic deployment of Schema.org JSON-LD markup
* Remote content publishing via REST API
* Schema health checks and management
* Secure application password authentication

No configuration needed. Install, activate, and AI-Recommendable will handle the rest.

== Installation ==

1. Upload the `ai-recommendable-connector` folder to `/wp-content/plugins/`
2. Activate the plugin through the 'Plugins' menu in WordPress
3. Generate an Application Password: Users → Profile → Application Passwords
4. Provide the username and application password to AI-Recommendable

== Frequently Asked Questions ==

= Do I need an API key? =
No. WordPress uses Application Passwords. Generate one in Users → Profile → Application Passwords.

= Is my site safe? =
Yes. The plugin only allows users with `edit_theme_options` capability to modify schema. Application passwords are scoped to specific users.

= What data does AI-Recommendable store? =
Schema markup is stored in your WordPress options table. No data is sent to external servers unless you explicitly deploy via the API.

== Changelog ==

= 1.0.0 =
* Initial release
* Schema markup deployment (header/footer)
* REST API endpoints for remote management
* Health check endpoint