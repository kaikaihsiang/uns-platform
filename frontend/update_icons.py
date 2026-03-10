file_path = "src/pages/NamespaceEditor.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

out_lines = []
in_import = False
found_icons = False

new_icons = [
    "    DatabaseOutlined,\n",
    "    ClockCircleOutlined,\n",
    "    ThunderboltOutlined,\n"
]

for line in lines:
    if "from 'antd';" in line:
        pass
    if line.startswith("import {"):
        in_import = True
    
    if in_import and "} from '@ant-design/icons';" in line:
        out_lines.extend(new_icons)
        in_import = False
    out_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(out_lines)

