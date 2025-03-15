"""Package setup for log-sentinel."""

from setuptools import find_packages, setup

setup(
    name="log-sentinel",
    version="0.1.0",
    description="Logging and metrics collection framework for scientific computing infrastructure",
    author="Madhumitha",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests", "tests.*", "examples"]),
    install_requires=[
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "log-sentinel=log_sentinel.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Logging",
        "Topic :: System :: Monitoring",
    ],
)
