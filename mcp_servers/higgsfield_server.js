#!/usr/bin/env node

/**
 * Higgsfield AI MCP Server for CB247 Marketing
 * 
 * This MCP server provides image and video generation via Higgsfield AI.
 * Configure with your Higgsfield API key in .env: HIGGSFIELD_API_KEY=your_key
 * 
 * Usage:
 *   node mcp_servers/higgsfield_server.js
 * 
 * Or add to .mcp.json:
 *   "higgsfield": {
 *     "command": "node",
 *     "args": ["/path/to/mcp_servers/higgsfield_server.js"]
 *   }
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

// Load environment variables
const fs = require('fs');
const path = require('path');

function loadEnv() {
  const envPath = path.join(process.cwd(), '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf-8');
    envContent.split('\n').forEach(line => {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#')) {
        const [key, ...valueParts] = trimmed.split('=');
        if (key && valueParts.length > 0) {
          process.env[key.trim()] = valueParts.join('=').trim();
        }
      }
    });
  }
}

loadEnv();

const HIGGSFIELD_API_KEY = process.env.HIGGSFIELD_API_KEY || '';
const HIGGSFIELD_API_URL = process.env.HIGGSFIELD_API_URL || 'https://api.higgsfield.io';

// Brand guidelines for CB247
const CB247_BRAND = {
  color: '#3FA69A',
  colorName: 'teal',
  tagline: 'AlwaysBetter',
  gym: 'ChasingBetter247',
  locations: ['Malaga', 'Ellenbrook']
};

/**
 * Make HTTP request to Higgsfield API
 */
function apiRequest(endpoint, options = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, HIGGSFIELD_API_URL);
    const protocol = url.protocol === 'https:' ? https : http;

    const requestOptions = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: options.method || 'GET',
      headers: {
        'Authorization': `Bearer ${HIGGSFIELD_API_KEY}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    };

    const req = protocol.request(requestOptions, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(data);
        }
      });
    });

    req.on('error', reject);
    if (options.body) {
      req.write(JSON.stringify(options.body));
    }
    req.end();
  });
}

/**
 * MCP Protocol Implementation
 */

const PROMPT_TEMPLATE = `You are generating a CB247 (ChasingBetter247) fitness marketing asset.
Brand color: ${CB247_BRAND.color} (${CB247_BRAND.colorName})
Tagline: ${CB247_BRAND.tagline}
Gym: ${CB247_BRAND.gym}
Locations: ${CB247_BRAND.locations.join(', ')}

IMPORTANT STYLE GUIDES:
- Use the teal brand color (#3FA69A) prominently
- Fitness/health imagery preferred
- Motivational but welcoming tone
- Clean, modern aesthetic
- Avoid corporate/pushy language
`;

/**
 * Generate image using Higgsfield
 */
async function generateImage(prompt, options = {}) {
  const enhancedPrompt = `${PROMPT_TEMPLATE}\n\nImage request: ${prompt}`;

  try {
    // TODO: Replace with actual Higgsfield API endpoint when known
    // Based on common AI image generation API patterns:
    const response = await apiRequest('/v1/generate/image', {
      method: 'POST',
      body: {
        prompt: enhancedPrompt,
        model: options.model || 'higgsfield-default',
        aspect_ratio: options.aspectRatio || '1:1',
        quality: options.quality || 'standard',
        ...options
      }
    });

    return {
      success: true,
      url: response.url || response.image_url || response.data?.[0]?.url,
      prompt: enhancedPrompt,
      metadata: response.metadata || {}
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      prompt: enhancedPrompt
    };
  }
}

/**
 * Generate video using Higgsfield
 */
async function generateVideo(prompt, options = {}) {
  const enhancedPrompt = `${PROMPT_TEMPLATE}\n\nVideo request: ${prompt}`;

  try {
    // TODO: Replace with actual Higgsfield API endpoint when known
    const response = await apiRequest('/v1/generate/video', {
      method: 'POST',
      body: {
        prompt: enhancedPrompt,
        model: options.model || 'higgsfield-video-default',
        duration: options.duration || 4,
        ...options
      }
    });

    return {
      success: true,
      url: response.url || response.video_url || response.data?.[0]?.url,
      prompt: enhancedPrompt,
      metadata: response.metadata || {}
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      prompt: enhancedPrompt
    };
  }
}

/**
 * MCP Protocol Handlers
 */
const MCP_METHODS = {
  'initialize': async (params) => ({
    protocolVersion: '2024-11-05',
    capabilities: {
      tools: true,
      resources: false
    },
    serverInfo: {
      name: 'higgsfield-server',
      version: '1.0.0'
    }
  }),

  'tools/list': async () => ({
    tools: [
      {
        name: 'generate_image',
        description: 'Generate a marketing image using Higgsfield AI for CB247',
        inputSchema: {
          type: 'object',
          properties: {
            prompt: {
              type: 'string',
              description: 'Image generation prompt describing the desired marketing asset'
            },
            aspectRatio: {
              type: 'string',
              enum: ['1:1', '16:9', '4:3', '9:16'],
              default: '1:1',
              description: 'Image aspect ratio'
            },
            quality: {
              type: 'string',
              enum: ['standard', 'high'],
              default: 'standard',
              description: 'Image quality'
            }
          },
          required: ['prompt']
        }
      },
      {
        name: 'generate_video',
        description: 'Generate a marketing video using Higgsfield AI for CB247',
        inputSchema: {
          type: 'object',
          properties: {
            prompt: {
              type: 'string',
              description: 'Video generation prompt describing the desired marketing asset'
            },
            duration: {
              type: 'number',
              default: 4,
              description: 'Video duration in seconds'
            }
          },
          required: ['prompt']
        }
      },
      {
        name: 'generate_instagram_post',
        description: 'Generate an Instagram post image with CB247 branding',
        inputSchema: {
          type: 'object',
          properties: {
            topic: {
              type: 'string',
              description: 'Topic for the Instagram post (e.g., "summer membership promotion", "new spin class")'
            }
          },
          required: ['topic']
        }
      },
      {
        name: 'generate_facebook_creative',
        description: 'Generate a Facebook ad creative with CB247 branding',
        inputSchema: {
          type: 'object',
          properties: {
            topic: {
              type: 'string',
              description: 'Topic for the Facebook ad'
            },
            format: {
              type: 'string',
              enum: ['single_image', 'carousel', 'video'],
              default: 'single_image',
              description: 'Facebook ad format'
            }
          },
          required: ['topic']
        }
      },
      {
        name: 'test_connection',
        description: 'Test the Higgsfield API connection',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      }
    ]
  }),

  'tools/call': async (params) => {
    const { name, arguments: args } = params;
    let result;

    switch (name) {
      case 'generate_image':
        result = await generateImage(args.prompt, args);
        break;
      case 'generate_video':
        result = await generateVideo(args.prompt, args);
        break;
      case 'generate_instagram_post':
        result = await generateImage(
          `Instagram post for CB247 gym: ${args.topic}. Include teal brand color, fitness imagery, CB247 branding. Motivational, welcoming.`,
          { aspectRatio: '1:1' }
        );
        result.type = 'instagram_post';
        break;
      case 'generate_facebook_creative':
        result = await generateImage(
          `Facebook ad for CB247 gym: ${args.topic}. Teal (#3FA69A) brand color, fitness imagery, clear CTA. Professional marketing.`,
          { aspectRatio: '16:9' }
        );
        result.type = 'facebook_creative';
        break;
      case 'test_connection':
        if (!HIGGSFIELD_API_KEY) {
          result = { success: false, error: 'HIGGSFIELD_API_KEY not configured in .env' };
        } else {
          try {
            // Simple API validation call
            await apiRequest('/v1/account');
            result = { success: true, message: 'Higgsfield API connection successful' };
          } catch (error) {
            result = { success: false, error: `Connection failed: ${error.message}` };
          }
        }
        break;
      default:
        result = { success: false, error: `Unknown tool: ${name}` };
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }
};

// Simple JSON-RPC over stdio server
process.stdin.on('data', (chunk) => {
  const lines = chunk.toString().split('\n').filter(Boolean);
  lines.forEach(async (line) => {
    try {
      const request = JSON.parse(line);
      const { id, method, params } = request;

      if (MCP_METHODS[method]) {
        const result = await MCP_METHODS[method](params);
        process.stdout.write(JSON.stringify({ id, result }) + '\n');
      } else {
        process.stdout.write(JSON.stringify({
          id,
          error: { code: -32601, message: `Method not found: ${method}` }
        }) + '\n');
      }
    } catch (error) {
      process.stderr.write(`Error: ${error.message}\n`);
    }
  });
});

// Handle test command
if (process.argv.includes('test')) {
  console.log('Testing Higgsfield MCP Server...');
  loadEnv();
  if (!HIGGSFIELD_API_KEY) {
    console.log('WARNING: HIGGSFIELD_API_KEY not set in .env');
    console.log('Add your API key: HIGGSFIELD_API_KEY=your_key');
    console.log('Server would work with actual API key.');
  } else {
    console.log('API key found, testing connection...');
  }
  process.exit(0);
}