import ast
import os
import sys
import importlib.util
from pathlib import Path
from typing import Set, List, Dict, Tuple
from collections import defaultdict, deque

class DependencyScanner:
    def __init__(self, scan_dir: str):
        self.scan_dir = Path(scan_dir)
        self.builtin_modules = set(sys.builtin_module_names)
        self.stdlib_modules = self._get_stdlib_modules()
        self.package_mappings = self._get_package_mappings()
        
        # 先初始化这些属性，再调用依赖它们的方法
        self.dependency_graph = defaultdict(set)
        self.file_to_module = {}
        
        # 现在可以安全地调用这个方法了
        self.local_modules = self._discover_local_modules()
        
    def _get_stdlib_modules(self) -> Set[str]:
        """获取标准库模块列表"""
        stdlib_modules = set()
        common_stdlib = {
            'os', 'sys', 'time', 'json', 're', 'math', 'random', 'datetime',
            'pathlib', 'collections', 'itertools', 'functools', 'operator',
            'traceback', 'logging', 'threading', 'subprocess', 'shutil',
            'tempfile', 'glob', 'pickle', 'csv', 'urllib', 'http', 'socket',
            'ssl', 'hashlib', 'base64', 'uuid', 'typing', 'abc', 'enum',
            'ctypes', 'queue', 'struct', 'array', 'bisect', 'heapq',
            'weakref', 'copy', 'pprint', 'reprlib', 'string', 'textwrap',
            'unicodedata', 'stringprep', 'readline', 'rlcompleter',
            'warnings', 'contextlib', 'io', 'email', 'mailcap', 'mailbox',
            'mimetypes', 'base64', 'binhex', 'binascii', 'quopri', 'uu',
            'html', 'xml', 'webbrowser', 'cgi', 'cgitb', 'wsgiref',
            'ftplib', 'poplib', 'imaplib', 'nntplib', 'smtplib', 'smtpd',
            'telnetlib', 'uuid', 'socketserver', 'http', 'xmlrpc',
            'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma', 'zlib',
            'hashlib', 'hmac', 'secrets', 'argparse', 'getopt', 'configparser',
            'netrc', 'xdrlib', 'plistlib', 'platform', 'errno', 'getpass',
            'termios', 'tty', 'pty', 'fcntl', 'pipes', 'resource', 'nis',
            'syslog', 'optparse', 'imp', 'importlib', 'concurrent', 'asyncio',
            'venv', 'ensurepip'
        }
        stdlib_modules.update(common_stdlib)
        return stdlib_modules
    
    def _get_package_mappings(self) -> Dict[str, str]:
        """获取import名称到PyPI包名的映射"""
        return {
            'maa': 'MaaFw',
            'win32api': 'pywin32',
            'win32con': 'pywin32', 
            'win32gui': 'pywin32',
            'win32process': 'pywin32',
            'win32ui': 'pywin32',
            'win32clipboard': 'pywin32',
            'win32file': 'pywin32',
            'win32pipe': 'pywin32',
            'win32event': 'pywin32',
            'win32security': 'pywin32',
            'win32service': 'pywin32',
            'win32serviceutil': 'pywin32',
            'pywintypes': 'pywin32',
            'pythoncom': 'pywin32',
            'PIL': 'Pillow',
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'yaml': 'PyYAML',
        }
    
    def _discover_local_modules(self) -> Set[str]:
        """发现所有本地模块"""
        local_modules = set()
        
        for item in self.scan_dir.rglob("*"):
            if item.is_file() and item.suffix == '.py':
                rel_path = item.relative_to(self.scan_dir)
                if rel_path.name == '__init__.py':
                    module_name = str(rel_path.parent).replace(os.sep, '.')
                    if module_name != '.':
                        local_modules.add(module_name)
                        parts = module_name.split('.')
                        for i in range(len(parts)):
                            local_modules.add('.'.join(parts[:i+1]))
                else:
                    module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
                    local_modules.add(module_name)
                    local_modules.add(rel_path.stem)
                    
                # 建立文件到模块的映射
                self.file_to_module[str(rel_path)] = rel_path.stem
        
        known_local = {
            'action', 'include', 'input', 'log', 'server', 'config', 'my_reco'
        }
        local_modules.update(known_local)
        return local_modules
    
    def _extract_imports_from_file(self, file_path: Path) -> Tuple[Set[str], Set[str]]:
        """从单个Python文件中提取import语句，返回(所有导入, 本地导入)"""
        all_imports = set()
        local_imports = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            current_module = self.file_to_module.get(str(file_path.relative_to(self.scan_dir)), '')
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        all_imports.add(module_name)
                        
                        # 构建依赖图
                        if current_module and module_name in self.local_modules:
                            self.dependency_graph[current_module].add(module_name)
                            local_imports.add(module_name)
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if node.level > 0:
                            # 相对导入处理
                            continue
                        module_name = node.module.split('.')[0]
                        all_imports.add(module_name)
                        
                        if current_module and module_name in self.local_modules:
                            self.dependency_graph[current_module].add(module_name)
                            local_imports.add(module_name)
                        
        except Exception as e:
            print(f"警告: 无法解析文件 {file_path}: {e}")
            
        return all_imports, local_imports
    
    def _detect_circular_dependencies(self) -> List[List[str]]:
        """检测循环依赖"""
        def dfs(node, path, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            cycles = []
            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    cycles.extend(dfs(neighbor, path.copy(), visited, rec_stack))
                elif neighbor in rec_stack:
                    # 找到循环
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            
            rec_stack.remove(node)
            return cycles
        
        visited = set()
        all_cycles = []
        
        for node in self.dependency_graph:
            if node not in visited:
                cycles = dfs(node, [], visited, set())
                all_cycles.extend(cycles)
        
        # 去重
        unique_cycles = []
        for cycle in all_cycles:
            # 标准化循环（从最小元素开始）
            min_idx = cycle.index(min(cycle))
            normalized = cycle[min_idx:] + cycle[:min_idx]
            if normalized not in unique_cycles:
                unique_cycles.append(normalized)
        
        return unique_cycles
    
    def scan_directory(self) -> Dict[str, any]:
        """扫描目录中的所有Python文件"""
        all_imports = set()
        file_imports = {}
        file_local_imports = {}
        
        print(f"发现的本地模块: {sorted(self.local_modules)}")
        
        for py_file in self.scan_dir.rglob("*.py"):
            if py_file.name.startswith('.'):
                continue
                
            imports, local_imports = self._extract_imports_from_file(py_file)
            rel_path = str(py_file.relative_to(self.scan_dir))
            file_imports[rel_path] = list(imports)
            file_local_imports[rel_path] = list(local_imports)
            all_imports.update(imports)
        
        # 检测循环依赖
        circular_deps = self._detect_circular_dependencies()
        
        third_party_imports = self._filter_third_party(all_imports)
        third_party_packages = self._map_to_packages(third_party_imports)
        
        return {
            'all_imports': sorted(all_imports),
            'file_imports': file_imports,
            'file_local_imports': file_local_imports,
            'third_party_imports': sorted(third_party_imports),
            'third_party_packages': sorted(third_party_packages),
            'local_modules': sorted(self.local_modules),
            'dependency_graph': dict(self.dependency_graph),
            'circular_dependencies': circular_deps
        }
    
    def _filter_third_party(self, imports: Set[str]) -> List[str]:
        """过滤出第三方库"""
        third_party = []
        
        for module in imports:
            if module in self.builtin_modules or module in self.stdlib_modules:
                continue
            if module in self.local_modules:
                continue
            if not module:
                continue
            third_party.append(module)
        
        return third_party
    
    def _map_to_packages(self, imports: List[str]) -> List[str]:
        """将import名称映射到PyPI包名"""
        packages = []
        for imp in imports:
            package_name = self.package_mappings.get(imp, imp)
            if package_name not in packages:
                packages.append(package_name)
        return packages

def main():
    scanner = DependencyScanner("agent")
    results = scanner.scan_directory()
    
    print("\n=== 依赖扫描结果 ===")
    print(f"第三方PyPI包: {results['third_party_packages']}")
    
    # 报告循环依赖
    if results['circular_dependencies']:
        print(f"\n⚠️  检测到 {len(results['circular_dependencies'])} 个循环依赖:")
        for i, cycle in enumerate(results['circular_dependencies'], 1):
            print(f"  {i}. {' → '.join(cycle)}")
    else:
        print("\n✅ 未检测到循环依赖")
    
    output_dir = Path("tools/deps")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成requirements.txt
    with open(output_dir / "requirements.txt", "w") as f:
        for package in results['third_party_packages']:
            f.write(f"{package}\n")
    
    print(f"\n已生成 tools/deps/requirements.txt，包含 {len(results['third_party_packages'])} 个依赖")
    
    # 生成详细报告
    with open(output_dir / "dependency_report.json", "w") as f:
        import json
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("已生成详细依赖报告: tools/deps/dependency_report.json")

if __name__ == "__main__":
    main()