file_path = "src/pages/NamespaceEditor.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace block matching our expected icons
pattern = r"from '@ant-design/icons';"
new_imports = """    DatabaseOutlined,
    ClockCircleOutlined,
    ThunderboltOutlined,
} from '@ant-design/icons';"""

# Check if they exist already to avoid duplicate
if "DatabaseOutlined" not in text:
    text = text.replace("} from '@ant-design/icons';", new_imports)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

