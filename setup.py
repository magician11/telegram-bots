from setuptools import setup, find_packages

setup(
    name="telegram-common",  # Package name (hyphenated)
    version="0.57",  # Version of your package
    description="A shared Python package for reusable Telegram bot functionality.",
    long_description=open("README.md").read(),  # Read the long description from README.md
    long_description_content_type="text/markdown",  # Specify the format of the long description
    author="Andrew Golightly",
    author_email="support@golightlyplus.com",
    url="https://saturn.tabby-alnair.ts.net/git/magician11/telegram-common",  # URL to your repository
    packages=find_packages(),  # Automatically find all packages (modules) in the project
    install_requires=[  # List of dependencies
        "python-telegram-bot",
        "fastapi",
        "openai",
        "requests",
    ],
    entry_points={
        'console_scripts': [
        'telegram-set-webhook=telegram_common.cli.set_webhook:main',
        ],
    },
    classifiers=[  # Metadata about your package
        "Development Status :: 3 - Alpha",  # Update as your project matures
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",  # Add Python 3.13 support
    ],
    python_requires=">=3.13",  # Minimum Python version required
)
