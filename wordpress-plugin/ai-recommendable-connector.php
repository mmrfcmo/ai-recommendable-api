<?php
/**
 * Plugin Name: AI-Recommendable Connector
 * Plugin URI: https://ai-recommendable.com
 * Description: Enables AI-Recommendable to deploy schema markup, content, and SEO improvements to your WordPress site.
 * Version: 1.0.0
 * Author: AI-Recommendable
 * License: GPL v2 or later
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

class AI_Recommendable_Connector {

    private $namespace = 'ai-recommendable/v1';

    public function __construct() {
        add_action('rest_api_init', array($this, 'register_routes'));
    }

    /**
     * Register REST API routes
     */
    public function register_routes() {
        // Deploy schema markup to site header
        register_rest_route($this->namespace, '/schema', array(
            'methods' => 'POST',
            'callback' => array($this, 'deploy_schema'),
            'permission_callback' => function () {
                return current_user_can('edit_theme_options');
            },
            'args' => array(
                'schema' => array(
                    'required' => true,
                    'type' => 'string',
                    'description' => 'JSON-LD schema markup to inject'
                ),
                'position' => array(
                    'required' => false,
                    'type' => 'string',
                    'enum' => array('header', 'footer'),
                    'default' => 'header'
                )
            ),
        ));

        // Get current schema status
        register_rest_route($this->namespace, '/schema', array(
            'methods' => 'GET',
            'callback' => array($this, 'get_schema_status'),
            'permission_callback' => function () {
                return current_user_can('edit_theme_options');
            },
        ));

        // Remove deployed schema
        register_rest_route($this->namespace, '/schema', array(
            'methods' => 'DELETE',
            'callback' => array($this, 'remove_schema'),
            'permission_callback' => function () {
                return current_user_can('edit_theme_options');
            },
        ));

        // Health check
        register_rest_route($this->namespace, '/health', array(
            'methods' => 'GET',
            'callback' => array($this, 'health_check'),
            'permission_callback' => '__return_true',
        ));
    }

    /**
     * Deploy schema markup by saving to WordPress options
     */
    public function deploy_schema($request) {
        $schema_json = $request->get_param('schema');
        $position = $request->get_param('position');

        // Validate JSON
        $decoded = json_decode($schema_json);
        if ($decoded === null && json_last_error() !== JSON_ERROR_NONE) {
            return new WP_Error('invalid_json', 'Invalid JSON-LD provided', array('status' => 400));
        }

        // Sanitize and store
        $sanitized = sanitize_text_field($schema_json);
        
        $existing = get_option('ai_recommendable_schemas', array());
        $existing[] = array(
            'schema' => $sanitized,
            'position' => $position,
            'added_at' => current_time('mysql'),
        );
        
        update_option('ai_recommendable_schemas', $existing);

        // Clear any caching plugins
        if (function_exists('wp_cache_flush')) {
            wp_cache_flush();
        }

        return array(
            'success' => true,
            'message' => 'Schema markup deployed successfully',
            'schemas_count' => count($existing),
            'preview' => substr($schema_json, 0, 100) . '...',
        );
    }

    /**
     * Get current schema status
     */
    public function get_schema_status() {
        $schemas = get_option('ai_recommendable_schemas', array());
        return array(
            'success' => true,
            'schemas_count' => count($schemas),
            'schemas' => $schemas,
        );
    }

    /**
     * Remove all deployed schemas
     */
    public function remove_schema() {
        delete_option('ai_recommendable_schemas');
        
        if (function_exists('wp_cache_flush')) {
            wp_cache_flush();
        }

        return array(
            'success' => true,
            'message' => 'All schema markup removed',
        );
    }

    /**
     * Simple health check
     */
    public function health_check() {
        return array(
            'success' => true,
            'plugin' => 'AI-Recommendable Connector',
            'version' => '1.0.0',
            'wp_version' => get_bloginfo('version'),
            'schemas_deployed' => count(get_option('ai_recommendable_schemas', array())),
        );
    }
}

/**
 * Inject schema markup into site header
 */
function ai_recommendable_inject_schemas() {
    $schemas = get_option('ai_recommendable_schemas', array());
    if (empty($schemas)) {
        return;
    }

    foreach ($schemas as $entry) {
        if ($entry['position'] === 'header') {
            $schema = $entry['schema'];
            // Un-sanitize for output (it was sanitized on save)
            $schema = html_entity_decode($schema);
            echo "\n<!-- AI-Recommendable Schema -->\n";
            echo '<script type="application/ld+json">' . "\n";
            echo $schema . "\n";
            echo '</script>' . "\n";
            echo "<!-- /AI-Recommendable Schema -->\n";
        }
    }
}
add_action('wp_head', 'ai_recommendable_inject_schemas', 1);

/**
 * Inject schema markup into site footer
 */
function ai_recommendable_inject_footer_schemas() {
    $schemas = get_option('ai_recommendable_schemas', array());
    if (empty($schemas)) {
        return;
    }

    foreach ($schemas as $entry) {
        if ($entry['position'] === 'footer') {
            $schema = $entry['schema'];
            $schema = html_entity_decode($schema);
            echo "\n<!-- AI-Recommendable Schema -->\n";
            echo '<script type="application/ld+json">' . "\n";
            echo $schema . "\n";
            echo '</script>' . "\n";
            echo "<!-- /AI-Recommendable Schema -->\n";
        }
    }
}
add_action('wp_footer', 'ai_recommendable_inject_footer_schemas', 1);

// Initialize the plugin
new AI_Recommendable_Connector();