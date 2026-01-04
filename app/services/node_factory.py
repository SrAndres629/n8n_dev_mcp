"""
Node Factory Service - Custom Node Creation
Enables scaffolding, building, and deploying custom n8n nodes.
"""
import json
import os
import subprocess
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.client import safe_tool
from app.core.logging import gateway_logger as logger


def _get_custom_nodes_dir() -> str:
    """Get custom nodes development directory."""
    custom_dir = os.path.join(settings.n8n_data_dir, "custom_nodes_dev")
    os.makedirs(custom_dir, exist_ok=True)
    return custom_dir


@safe_tool
async def scaffold_custom_node(
    node_name: str,
    description: str = "Custom n8n node",
    category: str = "Custom"
) -> str:
    """Create a boilerplate TypeScript custom node."""
    logger.info(f"Scaffolding custom node: {node_name}")
    
    try:
        custom_dir = _get_custom_nodes_dir()
        safe_name = "".join(c if c.isalnum() else "" for c in node_name)
        node_dir = os.path.join(custom_dir, safe_name)
        os.makedirs(node_dir, exist_ok=True)
        
        # Create TypeScript node file
        ts_content = f'''import {{
    IExecuteFunctions,
    INodeExecutionData,
    INodeType,
    INodeTypeDescription,
}} from 'n8n-workflow';

export class {safe_name} implements INodeType {{
    description: INodeTypeDescription = {{
        displayName: '{node_name}',
        name: '{safe_name.lower()}',
        group: ['transform'],
        version: 1,
        description: '{description}',
        defaults: {{
            name: '{node_name}',
        }},
        inputs: ['main'],
        outputs: ['main'],
        properties: [
            {{
                displayName: 'Input',
                name: 'input',
                type: 'string',
                default: '',
                placeholder: 'Enter value',
                description: 'Input value to process',
            }},
        ],
    }};

    async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {{
        const items = this.getInputData();
        const returnData: INodeExecutionData[] = [];

        for (let i = 0; i < items.length; i++) {{
            const input = this.getNodeParameter('input', i, '') as string;
            
            // Your custom logic here
            const result = {{
                processed: true,
                input: input,
                timestamp: new Date().toISOString(),
            }};

            returnData.push({{ json: result }});
        }}

        return [returnData];
    }}
}}
'''
        
        ts_path = os.path.join(node_dir, f"{safe_name}.node.ts")
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(ts_content)
        
        # Create package.json
        package_json = {
            "name": f"n8n-nodes-{safe_name.lower()}",
            "version": "0.1.0",
            "description": description,
            "main": "dist/index.js",
            "scripts": {
                "build": "tsc",
                "dev": "tsc --watch"
            },
            "n8n": {
                "nodes": [f"dist/{safe_name}.node.js"]
            },
            "devDependencies": {
                "typescript": "^5.0.0",
                "n8n-workflow": "^1.0.0"
            }
        }
        
        pkg_path = os.path.join(node_dir, "package.json")
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(package_json, f, indent=2)
        
        # Create tsconfig.json
        tsconfig = {
            "compilerOptions": {
                "target": "ES2020",
                "module": "commonjs",
                "outDir": "./dist",
                "strict": True,
                "esModuleInterop": True,
                "declaration": True
            },
            "include": ["*.ts"]
        }
        
        tsc_path = os.path.join(node_dir, "tsconfig.json")
        with open(tsc_path, "w", encoding="utf-8") as f:
            json.dump(tsconfig, f, indent=2)
        
        return json.dumps({
            "status": "success",
            "node_name": node_name,
            "safe_name": safe_name,
            "directory": node_dir,
            "files_created": [
                f"{safe_name}.node.ts",
                "package.json",
                "tsconfig.json"
            ],
            "next_steps": [
                "Edit the .ts file to add your logic",
                "Run: npm install",
                "Run: npm run build",
                "Copy dist/ to n8n custom nodes directory"
            ]
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def build_custom_node(node_name: str) -> str:
    """Build a custom node from TypeScript."""
    logger.info(f"Building custom node: {node_name}")
    
    try:
        custom_dir = _get_custom_nodes_dir()
        safe_name = "".join(c if c.isalnum() else "" for c in node_name)
        node_dir = os.path.join(custom_dir, safe_name)
        
        if not os.path.exists(node_dir):
            return json.dumps({
                "status": "error",
                "error": f"Node directory not found: {node_dir}"
            }, indent=2)
        
        # Install dependencies
        npm_install = subprocess.run(
            ["npm", "install"],
            cwd=node_dir,
            capture_output=True,
            text=True,
            shell=True,
            timeout=60
        )
        
        if npm_install.returncode != 0:
            return json.dumps({
                "status": "error",
                "stage": "npm_install",
                "error": npm_install.stderr[:500]
            }, indent=2)
        
        # Build
        npm_build = subprocess.run(
            ["npm", "run", "build"],
            cwd=node_dir,
            capture_output=True,
            text=True,
            shell=True,
            timeout=60
        )
        
        if npm_build.returncode != 0:
            return json.dumps({
                "status": "error",
                "stage": "build",
                "error": npm_build.stderr[:500]
            }, indent=2)
        
        # Check dist folder
        dist_dir = os.path.join(node_dir, "dist")
        if os.path.exists(dist_dir):
            files = os.listdir(dist_dir)
        else:
            files = []
        
        return json.dumps({
            "status": "success",
            "node_name": node_name,
            "build_output": npm_build.stdout[:300] if npm_build.stdout else "Build complete",
            "dist_files": files,
            "next_step": "Run deploy_custom_node to install in n8n"
        }, indent=2)
    except subprocess.TimeoutExpired:
        return json.dumps({"status": "error", "error": "Build timed out"}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def list_custom_nodes() -> str:
    """List all scaffolded custom nodes."""
    logger.info("Listing custom nodes")
    
    try:
        custom_dir = _get_custom_nodes_dir()
        
        if not os.path.exists(custom_dir):
            return json.dumps({
                "status": "success",
                "nodes": [],
                "directory": custom_dir
            }, indent=2)
        
        nodes = []
        for item in os.listdir(custom_dir):
            item_path = os.path.join(custom_dir, item)
            if os.path.isdir(item_path):
                pkg_path = os.path.join(item_path, "package.json")
                dist_path = os.path.join(item_path, "dist")
                
                node_info = {
                    "name": item,
                    "path": item_path,
                    "has_package_json": os.path.exists(pkg_path),
                    "is_built": os.path.exists(dist_path)
                }
                
                if os.path.exists(pkg_path):
                    try:
                        with open(pkg_path) as f:
                            pkg = json.load(f)
                        node_info["version"] = pkg.get("version")
                        node_info["description"] = pkg.get("description")
                    except:
                        pass
                
                nodes.append(node_info)
        
        return json.dumps({
            "status": "success",
            "directory": custom_dir,
            "node_count": len(nodes),
            "nodes": nodes
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def get_node_template(template_type: str = "http") -> str:
    """Get a node template for common patterns."""
    logger.info(f"Getting template: {template_type}")
    
    templates = {
        "http": '''// HTTP Request Template
async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];
    
    for (let i = 0; i < items.length; i++) {
        const url = this.getNodeParameter('url', i) as string;
        const response = await this.helpers.httpRequest({
            method: 'GET',
            url: url,
        });
        returnData.push({ json: response });
    }
    return [returnData];
}''',
        "transform": '''// Data Transform Template
async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    return [items.map(item => ({
        json: {
            ...item.json,
            transformed: true,
            processedAt: new Date().toISOString(),
        }
    }))];
}''',
        "filter": '''// Filter Template
async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const field = this.getNodeParameter('field', 0) as string;
    const value = this.getNodeParameter('value', 0) as string;
    
    const filtered = items.filter(item => item.json[field] === value);
    return [filtered];
}'''
    }
    
    template = templates.get(template_type, templates["transform"])
    
    return json.dumps({
        "status": "success",
        "template_type": template_type,
        "available_templates": list(templates.keys()),
        "template": template
    }, indent=2)
