import requests
import subprocess
import os
import re


# TODO: Ensure that we throw exit codes properly so we can report back to GitHub Actions!
# https://docs.github.com/en/free-pro-team@latest/actions/creating-actions/setting-exit-codes-for-actions
# TODO: Add logging
BASE_URL = 'https://api.github.com'
HEADERS = {
    'accept': 'application/vnd.github.v3+json',
    'agent': 'Shell Releaser'
}
SUBPROCESS_TIMEOUT = 30
TAR_ARCHIVE = 'tar_archive.tar.gz'

# GitHub Action Env Variables
GITHUB_TOKEN = os.getenv('INPUT_GITHUB_TOKEN')
OWNER = os.getenv('INPUT_OWNER')
OWNER_EMAIL = os.getenv('INPUT_OWNER_EMAIL')
REPO = os.getenv('INPUT_REPO')
BIN_INSTALL = os.getenv('INPUT_BIN_INSTALL')
HOMEBREW_TAP = os.getenv('INPUT_HOMEBREW_TAP')
HOMEBREW_FORMULA_FOLDER = os.getenv('INPUT_HOMEBREW_FORMULA_FOLDER')


def get_github_data(url):
    """Gets a repository's data
    """
    response = requests.get(
        url,
        headers=HEADERS
    )
    # TODO: Catch 404's here and other errors
    return response.json()


def get_latest_tar_archive(url):
    """Download the latest tar archive
    """
    # TODO: Add error handling here
    response = requests.get(
        url,
        headers=HEADERS,  # TODO: Are we sending the right headers here?
        stream=True
    )
    with open(TAR_ARCHIVE, 'wb') as tar_file:
        tar_file.write(response.raw.read())


def get_checksum(tar_file):
    """Gets the checksum of a file
    """
    # TODO: Create and upload a `checksums.txt` file to the release for the zip and tar archives
    output = subprocess.check_output(
        f'shasum -a 256 {tar_file}',
        stdin=None,
        stderr=None,
        shell=True,
        timeout=SUBPROCESS_TIMEOUT
    )
    checksum = output.decode().split()[0]
    checksum_file = output.decode().split()[1]  # TODO: Use this to craft the `checksums.txt` file  # noqa
    return checksum


def generate_formula(username, repo, version, description, checksum, bin_install, tar_url):
    """Generates the formula file for Homebrew

    We attempt to follow the guidelines here from `brew audit`:
    - Proper class name
    - 80 character or less desc field
    - Present homepage
    - URL points to the tar file
    - Checksum matches the url archive
    - Proper installable binary
    - Test is included
    """
    # TODO: Add test block in template
    repo_name_length = len(repo) + 2  # Offset for spaces and a buffer
    description_length = 80 - repo_name_length
    template = f"""# This file was generated by Shell Releaser. DO NOT EDIT.
  class {re.sub(r'[-_. ]+', '', repo.title())} < Formula
  desc "{description[:description_length].strip()}"
  homepage "https://github.com/{username}/{repo}"
  url "{tar_url}"
  sha256 "{checksum}"
  bottle :unneeded

  def install
    bin.install {bin_install.strip()}
  end
end
"""

    with open(f'new_{repo}.rb', 'w') as template_file:
        template_file.write(template)
    return template


def commit_formula(owner, owner_email, repo, version):
    """Commits the new formula to the remote Homebrew tap repo.

    1) Set global git config so this automated process can be attached to a user
    2) Clone the Homebrew tap repo
    3) Move our generated formula to the repo
    4) Commit and push the updated formula file to the repo
    """
    output = subprocess.check_output(
        (
            f'git config --global user.name "{owner}" && '
            f'git config --global user.email {owner_email} && '
            f'git clone https://{GITHUB_TOKEN}@github.com/{owner}/{HOMEBREW_TAP}.git && '
            f'mv new_{repo}.rb {HOMEBREW_TAP}/{HOMEBREW_FORMULA_FOLDER}/{repo}.rb && '
            f'cd {HOMEBREW_TAP} && '
            f'git add {HOMEBREW_FORMULA_FOLDER}/{repo}.rb && '
            f'git commit -m "Brew formula update for {repo} version {version}" && '
            f'git push https://{GITHUB_TOKEN}@github.com/{owner}/{HOMEBREW_TAP}.git'
        ),
        stdin=None,
        stderr=None,
        shell=True,
        timeout=SUBPROCESS_TIMEOUT
    )
    return output


def main():
    # TODO: Check to make sure that env variables are set
    repository = get_github_data(f'{BASE_URL}/repos/{OWNER}/{REPO}')
    # print(repository)
    description = repository['description']
    latest_release = get_github_data(f'{BASE_URL}/repos/{OWNER}/{REPO}/releases/latest')
    # print(latest_release)

    version = latest_release['name']
    tar_url = f'https://github.com/{OWNER}/{REPO}/archive/{version}.tar.gz'

    get_latest_tar_archive(tar_url)
    checksum = get_checksum(TAR_ARCHIVE)
    print(checksum)

    template = generate_formula(OWNER, REPO, version, description, checksum, BIN_INSTALL, tar_url)  # noqa
    # print(template)
    git = commit_formula(OWNER, OWNER_EMAIL, REPO, version)
    print(git)
    print(f'Shell Releaser released {version} of {REPO} successfully!')


if __name__ == '__main__':
    main()
