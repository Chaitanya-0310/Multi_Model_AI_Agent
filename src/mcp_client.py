"""
MCP (Model Context Protocol) Client for Google Docs Integration

This module provides a client to communicate with MCP servers,
specifically for Google Drive/Docs operations.
"""

import subprocess
import json
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger("MCPClient")

class MCPClient:
    """Client for interacting with MCP servers."""
    
    def __init__(self, server_config: Dict[str, Any]):
        """
        Initialize MCP client with server configuration.
        
        Args:
            server_config: Configuration dict with 'command', 'args', and 'env'
        """
        self.command = server_config.get("command")
        self.args = server_config.get("args", [])
        self.env = server_config.get("env", {})
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        
    def _prepare_env(self) -> Dict[str, str]:
        """Prepare environment variables for the MCP server."""
        env = os.environ.copy()
        
        # Resolve environment variable placeholders
        for key, value in self.env.items():
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved = os.environ.get(env_var, "")
                env[key] = resolved
            else:
                env[key] = value
        
        return env
    
    def start_server(self) -> bool:
        """
        Start the MCP server process.
        
        Returns:
            True if server started successfully, False otherwise
        """
        if self.is_running:
            logger.info("MCP server already running")
            return True
            
        try:
            env = self._prepare_env()
            
            logger.info(f"Starting MCP server: {self.command} {' '.join(self.args)}")
            
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1
            )
            
            self.is_running = True
            logger.info("MCP server started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call (e.g., 'create_file', 'write_file')
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool response or None if failed
        """
        if not self.is_running or not self.process:
            logger.error("MCP server not running")
            return None
        
        try:
            # Prepare JSON-RPC request
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": 1
            }
            
            # Send request
            request_str = json.dumps(request) + "\n"
            self.process.stdin.write(request_str)
            self.process.stdin.flush()
            
            # Read response
            response_str = self.process.stdout.readline()
            response = json.loads(response_str)
            
            if "error" in response:
                logger.error(f"MCP tool error: {response['error']}")
                return None
            
            return response.get("result")
            
        except Exception as e:
            logger.error(f"Error calling MCP tool: {e}")
            return None
    
    def create_google_doc(self, title: str, content: str) -> Optional[tuple]:
        """
        Create a Google Doc using MCP.
        
        Args:
            title: Document title
            content: Document content
            
        Returns:
            Tuple of (doc_id, doc_url) or None if failed
        """
        try:
            # First, create the file
            create_result = self.call_tool("create_file", {
                "name": title,
                "mimeType": "application/vnd.google-apps.document"
            })
            
            if not create_result:
                logger.error("Failed to create Google Doc via MCP")
                return None
            
            doc_id = create_result.get("id")
            doc_url = create_result.get("webViewLink")
            
            # Then, write content to it
            if content:
                write_result = self.call_tool("write_file", {
                    "id": doc_id,
                    "content": content
                })
                
                if not write_result:
                    logger.warning(f"Created doc but failed to write content: {doc_id}")
            
            logger.info(f"Created Google Doc via MCP: {doc_url}")
            return doc_id, doc_url
            
        except Exception as e:
            logger.error(f"Error creating Google Doc via MCP: {e}")
            return None
    
    def stop_server(self):
        """Stop the MCP server process."""
        if self.process and self.is_running:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info("MCP server stopped")
            except Exception as e:
                logger.error(f"Error stopping MCP server: {e}")
                try:
                    self.process.kill()
                except:
                    pass
            finally:
                self.is_running = False
                self.process = None


def load_mcp_config(config_path: str = "mcp_config.json") -> Optional[Dict[str, Any]]:
    """
    Load MCP configuration from file.
    
    Args:
        config_path: Path to MCP config file
        
    Returns:
        Configuration dict or None if failed
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load MCP config: {e}")
        return None


def get_gdrive_client() -> Optional[MCPClient]:
    """
    Get configured MCP client for Google Drive.
    
    Returns:
        MCPClient instance or None if configuration failed
    """
    config = load_mcp_config()
    if not config or "gdrive" not in config.get("mcpServers", {}):
        logger.error("Google Drive MCP server not configured")
        return None
    
    server_config = config["mcpServers"]["gdrive"]
    client = MCPClient(server_config)
    
    return client
