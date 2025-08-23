from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text()

setup(
    name="infra-health-checker",
    version="1.0.0",
    description="Infrastructure health monitoring toolkit with Bash checks and Python reporting",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Madhumitha",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    package_data={
        "health_checker": ["../templates/*.html", "../config.yaml.example"],
    },
    install_requires=[
        "PyYAML>=6.0.1",
        "Jinja2>=3.1.3",
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0.0", "pytest-cov>=4.1.0"],
    },
    entry_points={
        "console_scripts": [
            "health-checker=health_checker.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Unix Shell",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: MIT License",
    ],
)
