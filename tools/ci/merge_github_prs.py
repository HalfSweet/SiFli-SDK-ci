import os
import sys
from github import Github
import gitlab
import git

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
GITLAB_BRANCH = os.environ.get('GITLAB_BRANCH', 'main')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
GITLAB_URL = os.environ.get('GITLAB_URL')
GITLAB_TOKEN = os.environ.get('GITLAB_TOKEN')
GITLAB_REPO = os.environ.get('GITLAB_REPO')

if not all([GITHUB_TOKEN, GITHUB_REPO, GITLAB_URL, GITLAB_TOKEN, GITLAB_REPO]):
    print('缺少必要的环境变量')
    sys.exit(1)

g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# 获取所有可合并的PR（此处假设label为'queue-for-merge'）
prs = repo.get_pulls(state='open', base=GITHUB_BRANCH)
queue_prs = [pr for pr in prs]

if not queue_prs:
    print('没有待合并的PR')
    sys.exit(0)

# 连接GitLab
gl = gitlab.Gitlab(f"https://{GITLAB_URL}", private_token=GITLAB_TOKEN)
project = gl.projects.get(GITLAB_REPO)
gitlab_mrs = project.mergerequests.list(state='opened', search='(GitHub PR)')

for pr in queue_prs:
    # 查找对应的Gitlab MR
    gitlab_mr = None
    for mr in gitlab_mrs:
        if pr.title in mr.title:
            gitlab_mr = mr
            break
    else:
        print(f'没有找到对应的GitLab MR，跳过PR #{pr.number}')
        continue

    # 判断Gitlab MR是否可合并
    if not gitlab_mr.detailed_merge_status == 'mergeable':
        print(f'GitLab MR #{gitlab_mr.iid} 不可合并，跳过PR #{pr.number}')
        continue
    try:
        pr.merge(merge_method='squash')
        print(f'PR #{pr.number} 合并成功')
    except Exception as e:
        print(f'PR #{pr.number} 合并失败: {e}')
        continue
    # 关闭GitLab MR
    try:
        gitlab_mr.state_event = 'close'
        gitlab_mr.save()
        print(f'GitLab MR #{gitlab_mr.iid} 已关闭')
    except Exception as e:
        print(f'关闭GitLab MR #{gitlab_mr.iid} 失败: {e}')

# 将修改之后的代码推送到Gitlab
try:
    git_repo = git.Repo(os.getcwd())
    gitlab_url = f'https://{GITLAB_TOKEN}@{GITLAB_URL}/{GITLAB_REPO}.git'
    git_repo.git.pull(gitlab_url, f'{GITLAB_BRANCH}:{GITHUB_BRANCH}', force=True)
    print('代码已推送到GitLab')
except Exception as e:
    print(f'推送到GitLab失败: {e}')
    sys.exit(1)