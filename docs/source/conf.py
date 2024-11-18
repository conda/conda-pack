import alabaster

import conda_pack

# Project settings
project = 'conda-pack'
copyright = '2017, Jim Crist'
author = 'Jim Crist'
release = version = conda_pack.__version__

source_suffix = '.rst'
master_doc = 'index'
language = None
pygments_style = 'sphinx'
exclude_patterns = []

# Sphinx Extensions
extensions = ['sphinx.ext.autodoc',
              'numpydoc',
              'sphinxcontrib.autoprogram']

numpydoc_show_class_members = False

# Sphinx Theme
html_theme = 'alabaster'
html_theme_path = [alabaster.get_path()]
templates_path = ['_templates']
html_static_path = ['_static']
html_theme_options = {
    'description': 'A tool for packaging and distributing conda environments.',
    'github_button': True,
    'github_count': False,
    'github_user': 'conda',
    'github_repo': 'conda-pack',
    'travis_button': False,
    'show_powered_by': False,
    'page_width': '960px',
    'sidebar_width': '200px',
    'code_font_size': '0.8em'
}
html_sidebars = {
    '**': ['about.html',
           'navigation.html',
           'help.html',
           'searchbox.html']
}
