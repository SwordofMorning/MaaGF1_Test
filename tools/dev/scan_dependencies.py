import ast
import os
import sys
import importlib.util
from pathlib import Path
from typing import Set, List, Dict

class DependencyScanner:
    def __init__(self, scan_dir: str):
        self.scan_dir = Path(scan_dir)
        self.builtin_modules = set(sys.builtin_module_names)
        self.stdlib_modules = self._get_stdlib_modules()
        
    def _get_stdlib_modules(self) -> Set[str]:
        """获取标准库模块列表"""
        stdlib_modules = set()
        common_stdlib = {
            'os', 'sys', 'time', 'json', 're', 'math', 'random', 'datetime',
            'pathlib', 'collections', 'itertools', 'functools', 'operator',
            'traceback', 'logging', 'threading', 'subprocess', 'shutil',
            'tempfile', 'glob', 'pickle', 'csv', 'urllib', 'http', 'socket',
            'ssl', 'hashlib', 'base64', 'uuid', 'typing', 'abc', 'enum'
        }
        stdlib_modules.update(common_stdlib)
        return stdlib_modules
    
    def _extract_imports_from_file(self, file_path: Path) -> Set[str]:
        """从单个Python文件中提取import语句"""
        imports = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
                        
        except Exception as e:
            print(f"警告: 无法解析文件 {file_path}: {e}")
            
        return imports
    
    def scan_directory(self) -> Dict[str, List[str]]:
        """扫描目录中的所有Python文件"""
        all_imports = set()
        file_imports = {}
        
        for py_file in self.scan_dir.rglob("*.py"):
            if py_file.name.startswith('.'):
                continue
                
            imports = self._extract_imports_from_file(py_file)
            file_imports[str(py_file.relative_to(self.scan_dir))] = list(imports)
            all_imports.update(imports)
        
        return {
            'all_imports': list(all_imports),
            'file_imports': file_imports,
            'third_party': self._filter_third_party(all_imports)
        }
    
    def _filter_third_party(self, imports: Set[str]) -> List[str]:
        """过滤出第三方库"""
        third_party = []
        
        for module in imports:
            # 跳过内置模块和标准库
            if module in self.builtin_modules or module in self.stdlib_modules:
                continue
                
            # 跳过本地模块
            if self._is_local_module(module):
                continue
                
            third_party.append(module)
        
        return sorted(third_party)
    
    def _is_local_module(self, module_name: str) -> bool:
        """检查是否为本地模块"""
        # 检查是否存在对应的.py文件
        possible_paths = [
            self.scan_dir / f"{module_name}.py",
            self.scan_dir / module_name / "__init__.py"
        ]
        
        return any(path.exists() for path in possible_paths)

def main():
    scanner = DependencyScanner("agent")
    results = scanner.scan_directory()
    
    print("=== 依赖扫描结果 ===")
    print(f"发现的第三方库: {results['third_party']}")
    
    output_dir = Path("tools/py_deps")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成requirements.txt
    with open(output_dir / "requirements.txt", "w") as f:
        for lib in results['third_party']:
            f.write(f"{lib}\n")
    
    print(f"已生成 tools/py_deps/requirements.txt，包含 {len(results['third_party'])} 个依赖")
    
    # 生成dependency_report.json
    with open(output_dir / "dependency_report.json", "w") as f:
        import json
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()