from setuptools import setup, find_packages

setup(
    name="voxdeck",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        line.strip()
        for line in open("requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    entry_points={
        'console_scripts': [
            'voxdeck=voxdeck.cli:cli',
        ],
    },
    python_requires=">=3.8",
    author="Jai Bhatia",
    description="Voice control for Google Slides",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="google-slides voice-control presentation",
    project_urls={
        "Source": "https://github.com/yourusername/voxdeck",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Office/Business :: Presentation",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 