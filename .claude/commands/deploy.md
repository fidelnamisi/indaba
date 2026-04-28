Deploy Indaba to EC2.

Merge the current branch into `main` and push. This triggers the GitHub Actions `deploy.yml` workflow, which SSHs into EC2 and restarts the app automatically.

Steps:
1. Run `git branch --show-current` to capture the current branch name
2. `git checkout main`
3. `git merge <current-branch> --no-edit`
4. `git push origin main`
5. `git checkout <original-branch>` to return to the working branch
6. Confirm with a one-line message: "Deployed: <branch> → main → EC2 deploy triggered."

If already on main, just push: `git push origin main`.
If there is nothing new to merge (branch is already in main), say so and skip.
