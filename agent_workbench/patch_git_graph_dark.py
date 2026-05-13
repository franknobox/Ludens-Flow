import os

dark_css_file = r'agent_workbench/web/src/styles/theme-dark.css'
with open(dark_css_file, 'r', encoding='utf-8', errors='ignore') as f:
    dark_css_content = f.read()

new_dark_css = """
/* Git Graph Dark Mode Overrides */
.github-graph-container {
  background: rgba(30, 35, 45, 0.4) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
}

.git-graph-label {
  fill: #d8dee9 !important;
}

.git-graph-hash {
  fill: #81a1c1 !important;
}

.github-graph-svg circle {
  fill: #2e3440 !important;
}

.github-graph-svg circle[r="14"] {
  fill: #5e81ac !important;
  stroke: #eceff4 !important;
}
"""

if '.git-graph-label' not in dark_css_content:
    with open(dark_css_file, 'a', encoding='utf-8') as f:
        f.write("\n" + new_dark_css)
    print("theme-dark.css updated.")
