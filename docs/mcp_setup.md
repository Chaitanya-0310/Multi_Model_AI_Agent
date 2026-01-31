# MCP Server Setup Guide for Google Docs Integration

## Overview

This guide explains how to set up **Model Context Protocol (MCP)** servers to integrate Google Docs functionality into your agentic workflow. MCP provides a standardized way for AI applications to interact with external services.

## What is MCP?

**Model Context Protocol (MCP)** is an open protocol that enables:
- Standardized integration between AI applications and external services
- Server-client architecture where MCP servers expose tools and resources
- Communication via JSON-RPC over stdio, SSE, or other transports

In our case, we'll use the `@modelcontextprotocol/server-gdrive` MCP server to interact with Google Drive and Google Docs.

## Prerequisites

### 1. Install Node.js

MCP servers for Google Workspace run on Node.js.

**Windows:**
```powershell
# Download and install from official website
# Visit: https://nodejs.org/

# Or use winget
winget install OpenJS.NodeJS

# Verify installation
node --version
npm --version
```

### 2. Set Up Google Cloud Project

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**

2. **Create a new project** (or select existing):
   - Click "Select a Project" → "New Project"
   - Name: "Marketing Campaign MCP"
   - Click "Create"

3. **Enable Google Docs & Drive APIs**:
   ```
   Navigate to: APIs & Services → Library
   
   Search and enable:
   - Google Docs API
   - Google Drive API
   ```

4. **Create OAuth 2.0 Credentials**:
   - Go to: APIs & Services → Credentials
   - Click: "+ CREATE CREDENTIALS" → "OAuth client ID"
   - Application type: "Desktop app"
   - Name: "Marketing Campaign MCP Client"
   - Click "Create"
   - **Download the JSON file** and save as `credentials.json` in your project root

5. **Configure OAuth Consent Screen**:
   - Go to: APIs & Services → OAuth consent screen
   - User Type: "External" (or "Internal" if using Google Workspace)
   - Fill required fields (App name, User support email, Developer email)
   - Add scopes:
     - `https://www.googleapis.com/auth/documents`
     - `https://www.googleapis.com/auth/drive.file`
   - Save and continue

## MCP Server Installation

### Option 1: Using npx (Recommended)

The MCP server will be auto-installed when needed using `npx`. No manual installation required!

### Option 2: Global Installation

```powershell
npm install -g @modelcontextprotocol/server-gdrive
```

## Configuration

### 1. Create MCP Configuration File

The configuration file is already created at `mcp_config.json`:

```json
{
  "mcpServers": {
    "gdrive": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-gdrive"
      ],
      "env": {
        "GDRIVE_CLIENT_ID": "${GDRIVE_CLIENT_ID}",
        "GDRIVE_CLIENT_SECRET": "${GDRIVE_CLIENT_SECRET}",
        "GDRIVE_REDIRECT_URI": "http://localhost:3000/oauth2callback"
      }
    }
  }
}
```

### 2. Set Environment Variables

Extract the credentials from your `credentials.json` file and add to `.env`:

```env
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key_here

# Google OAuth for MCP (from credentials.json)
GDRIVE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GDRIVE_CLIENT_SECRET=your_client_secret
```

**Finding your credentials:**
Open `credentials.json` and look for:
```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID_HERE",
    "client_secret": "YOUR_CLIENT_SECRET_HERE"
  }
}
```

## Testing MCP Connection

### 1. Test the MCP Server Directly

```powershell
# Run the MCP server
npx -y @modelcontextprotocol/server-gdrive

# You should see output indicating the server is running
```

Press `Ctrl+C` to stop.

### 2. Test via Python Integration

After implementation, run:

```powershell
python tests/test_mcp_integration.py
```

## Available MCP Tools

The Google Drive MCP server provides these tools:

| Tool | Description |
|------|-------------|
| `create_file` | Create a new Google Doc |
| `write_file` | Write content to a Google Doc |
| `read_file` | Read content from a Google Doc |
| `search_files` | Search for files in Google Drive |
| `list_files` | List files in a folder |

## Authentication Flow

1. **First Run**: When you first use the MCP server:
   - A browser window will open
   - Sign in with your Google account
   - Grant permissions to the app
   - Token will be saved for future use

2. **Subsequent Runs**: Authentication token is reused automatically

## Troubleshooting

### Error: "Command 'npx' not found"

**Solution**: Install Node.js or add it to your PATH:
```powershell
$env:Path += ";C:\Program Files\nodejs\"
```

### Error: "OAuth consent screen not configured"

**Solution**: Complete the OAuth Consent Screen setup in Google Cloud Console

### Error: "Access blocked: This app's request is invalid"

**Solution**: 
1. Ensure redirect URI matches exactly: `http://localhost:3000/oauth2callback`
2. Add this URI in Google Cloud Console → Credentials → Your OAuth Client → Authorized redirect URIs

### Error: "Token expired"

**Solution**: Delete the token file and re-authenticate:
```powershell
Remove-Item token.pickle -ErrorAction SilentlyContinue
```

## Using MCP vs Direct Google API

### MCP Advantages:
- ✅ Standardized protocol for multiple integrations
- ✅ Easy to add more MCP servers (Gmail, Calendar, Slack, etc.)
- ✅ Better separation of concerns
- ✅ Community-maintained servers

### Direct API Advantages:
- ✅ Fewer dependencies
- ✅ More control over API calls
- ✅ No additional server process

**Our Implementation**: We support **both** approaches with automatic fallback!

## Next Steps

1. Follow this guide to set up Google Cloud credentials
2. Test the MCP server connection
3. Run the updated Streamlit app
4. The app will automatically use MCP when available, fallback to direct API otherwise

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [MCP Google Drive Server](https://github.com/modelcontextprotocol/servers)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Google OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
