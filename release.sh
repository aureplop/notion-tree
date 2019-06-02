set -e

# Ensure build tools are installed and up-to-date.
pip install -U pip setuptools wheel

# Clean existing builds
rm -rf dist/

# Detect version.
version=$(grep version notiontree/__init__.py | sed -E 's/.*[\"'"'"'](.*)[\"'"'"'].*/\1/')

# Create GitHub release.
git tag -a "$version" -m "$version"

# Build wheel (Python packaging).
python setup.py bdist_wheel

# Publish on TestPyPI.
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Publish on PyPI.
twine upload dist/*

# Publish on GitHub.
git push origin "$version"
