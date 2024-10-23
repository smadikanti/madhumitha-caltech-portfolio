from setuptools import setup, find_packages

setup(
    name="fits-image-processor",
    version="1.0.0",
    description="FITS image processing toolkit for astronomical image analysis",
    author="Madhumitha",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "astropy>=5.3",
        "numpy>=1.24",
        "matplotlib>=3.7",
        "pillow>=10.0",
    ],
    extras_require={
        "dev": ["pytest>=7.4"],
    },
    entry_points={
        "console_scripts": [
            "fits-processor=fits_processor.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Astronomy",
        "License :: OSI Approved :: BSD License",
    ],
)
