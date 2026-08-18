# Usage Examples

Practical examples for using the Ignition MCP Server's 37 tools. For full parameter
details on any tool, see [api-reference.md](api-reference.md).

## Table of Contents

- [Getting Started](#getting-started)
- [Gateway Health](#gateway-health)
- [Project Operations](#project-operations)
- [Tag Browsing and Values](#tag-browsing-and-values)
- [Tag Configuration](#tag-configuration)
- [Alarms](#alarms)
- [Tag History](#tag-history)
- [Natural Language in Claude](#natural-language-in-claude)
- [Best Practices](#best-practices)

## Getting Started

### First Connection Check

Confirm the server can reach your gateway:

```python
{"tool": "get_gateway_info", "arguments": {}}
```

**Example response**:
```json
{
  "name": "MyGateway",
  "edition": "standard",
  "ignitionVersion": "8.3.8",
  "license": {"mode": "Trial", "expirationDate": "..."}
}
```

## Gateway Health

```python
# Module health
{"tool": "get_module_health", "arguments": {}}

# Database connections
{"tool": "get_database_connections", "arguments": {}}

# OPC-UA/COM connections
{"tool": "get_opc_connections", "arguments": {}}

# CPU, memory, threads, sessions
{"tool": "get_system_metrics", "arguments": {}}

# Recent errors
{"tool": "get_gateway_logs", "arguments": {"level": "ERROR", "limit": 20}}
```

## Project Operations

### List and Inspect

```python
{"tool": "list_projects", "arguments": {}}

{"tool": "get_project", "arguments": {"name": "MyProject"}}
```

### Create, Copy, Rename, Delete

```python
{"tool": "create_project", "arguments": {
  "name": "TestEnvironment",
  "title": "Test Environment",
  "description": "Created via MCP",
  "enabled": True
}}

{"tool": "copy_project", "arguments": {
  "source_name": "Production",
  "new_name": "Production_Backup"
}}

{"tool": "rename_project", "arguments": {
  "current_name": "Production_Backup",
  "new_name": "Production_Archive"
}}

# Irreversible — export first if you might need it back
{"tool": "delete_project", "arguments": {"name": "Production_Archive"}}
```

### Export / Import

```python
export = {"tool": "export_project", "arguments": {"name": "Production"}}
# -> {"filename": ..., "content_base64": ..., "size_bytes": ...}

{"tool": "import_project", "arguments": {
  "name": "Production_Restored",
  "zip_base64": export["content_base64"],
  "overwrite": False
}}
```

### Project Resources

```python
{"tool": "list_project_resources", "arguments": {
  "project": "MyProject",
  "path_prefix": "com.inductiveautomation.perspective/views"
}}

{"tool": "get_project_resource", "arguments": {
  "project": "MyProject",
  "resource_path": "com.inductiveautomation.perspective/views/Home/view.json"
}}

# Overwrites without confirmation — check the current content first
{"tool": "set_project_resource", "arguments": {
  "project": "MyProject",
  "resource_path": "com.inductiveautomation.ignition/script-python/shared/utils/code.py",
  "content": "def hello():\n    return 'hi'\n"
}}
```

## Tag Browsing and Values

### Browse Structure (no WebDev needed)

```python
{"tool": "browse_tags", "arguments": {"path": "[default]", "depth": 2}}

{"tool": "list_tag_providers", "arguments": {}}
```

### Read / Write Runtime Values (requires `IGNITION_MCP_WEBDEV_TAG_ENDPOINT`)

```python
{"tool": "read_tags", "arguments": {
  "tag_paths": ["[default]Line1/Speed", "[default]Line1/Running"]
}}

{"tool": "write_tag", "arguments": {
  "tag_path": "[default]Line1/Setpoint",
  "value": 42.5,
  "data_type": "Float8"
}}
```

If the WebDev endpoint isn't configured, these return a setup-guidance error instead of
data — see [webdev-setup.md](webdev-setup.md).

## Tag Configuration

Requires `IGNITION_MCP_WEBDEV_TAG_CONFIG_ENDPOINT`.

```python
{"tool": "create_tags", "arguments": {
  "tags": [{"name": "NewTag", "tagType": "AtomicTag", "dataType": "Float8"}],
  "provider": "default"
}}

{"tool": "get_tag_config", "arguments": {"tag_path": "[default]Line1/Speed"}}

{"tool": "edit_tags", "arguments": {
  "tags": [{"name": "Speed", "path": "Line1", "tooltip": "Belt speed, m/s"}]
}}

# Irreversible
{"tool": "delete_tags", "arguments": {"tag_paths": ["[default]Line1/OldTag"]}}

{"tool": "list_udt_types", "arguments": {"provider": "default"}}
{"tool": "get_udt_definition", "arguments": {"udt_path": "[default]_types_/Motor"}}
```

## Alarms

Requires `IGNITION_MCP_WEBDEV_ALARM_ENDPOINT`.

```python
{"tool": "get_active_alarms", "arguments": {
  "priority_filter": "High",
  "state_filter": "ActiveUnacked"
}}

{"tool": "get_alarm_history", "arguments": {
  "start_time": "2026-08-06T00:00:00Z",
  "end_time": "2026-08-07T00:00:00Z",
  "max_results": 100
}}

{"tool": "acknowledge_alarms", "arguments": {
  "event_ids": ["<uuid-from-get_active_alarms>"],
  "ack_note": "Investigated, resetting"
}}
```

## Tag History

Requires `IGNITION_MCP_WEBDEV_TAG_HISTORY_ENDPOINT`.

```python
{"tool": "get_tag_history", "arguments": {
  "tag_paths": ["[default]Line1/Speed"],
  "start_time": "2026-08-06T00:00:00Z",
  "end_time": "2026-08-07T00:00:00Z",
  "aggregation": "Average",
  "interval_ms": 60000
}}
```

## Natural Language in Claude

When connected via Claude Code or Claude Desktop, you don't need to write tool-call JSON
directly — plain language works:

- "List all Ignition projects"
- "What's the current CPU and memory usage on the gateway?"
- "Show me any ERROR-level logs from the last hour"
- "Browse the tag tree under the default provider"
- "Read the value of [default]Line1/Speed" *(requires WebDev tag endpoint)*
- "Are there any active high-priority alarms?" *(requires WebDev alarm endpoint)*
- "Export the Production project"

Claude maps these to the appropriate tool call(s) automatically.

## Best Practices

### 1. Export Before Destructive Operations

```python
backup = {"tool": "export_project", "arguments": {"name": "Production"}}
# then proceed with delete_project / import_project / overwrite
```

### 2. Check WebDev Configuration First

If a tag/alarm/history tool errors immediately with a setup message rather than gateway
data, that's expected when the corresponding `IGNITION_MCP_WEBDEV_*_ENDPOINT` is unset —
it's not a bug. See [webdev-setup.md](webdev-setup.md).

### 3. Batch Reads, Not Loops

`read_tags` and `get_tag_history` both accept a list of paths — prefer one call with
many paths over many single-tag calls.

### 4. Regular Health Checks

```python
health_checks = [
    {"tool": "get_gateway_info", "arguments": {}},
    {"tool": "get_module_health", "arguments": {}},
    {"tool": "get_gateway_logs", "arguments": {"level": "ERROR", "limit": 10}},
]
```
