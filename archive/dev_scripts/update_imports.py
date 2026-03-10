import re

file_path = "src/pages/NamespaceEditor.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace the specific import block
target_import = """import {
    ApartmentOutlined,
    PlusOutlined,
    EditOutlined,
    DeleteOutlined,
    ReloadOutlined,
    SettingOutlined,
} from '@ant-design/icons';"""

new_import = """import {
    ApartmentOutlined,
    PlusOutlined,
    EditOutlined,
    DeleteOutlined,
    ReloadOutlined,
    SettingOutlined,
    DatabaseOutlined,
    ClockCircleOutlined,
    ThunderboltOutlined
} from '@ant-design/icons';"""

text = text.replace(target_import, new_import)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

