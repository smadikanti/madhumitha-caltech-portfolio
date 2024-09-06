"""Package configuration for stellar-data-pipeline."""

from setuptools import find_packages, setup

setup(
    name="stellar-data-pipeline",
    version="1.0.0",
    description="NASA Exoplanet Archive data ingestion pipeline",
    author="Madhumitha",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "requests>=2.31.0",
        "psycopg2-binary>=2.9.9",
        "PyYAML>=6.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "stellar-pipeline=stellar_pipeline.__main__:main",
        ],
    },
)
