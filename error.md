2026-05-08T09:28:43.725057Z 00O Running with gitlab-runner 18.11.1 (5265d41d)
2026-05-08T09:28:43.725057Z 00O   on little_ym3 Bap6ZvsMt, system ID: s_34480d4f5a50
2026-05-08T09:28:43.725057Z 00O section_start:1778232523:prepare_executor
2026-05-08T09:28:43.725057Z 00O+Preparing the "shell" executor
2026-05-08T09:28:43.725057Z 00O Using Shell (pwsh) executor...
2026-05-08T09:28:43.725057Z 00O section_end:1778232523:prepare_executor
2026-05-08T09:28:43.725057Z 00O+section_start:1778232523:prepare_script
2026-05-08T09:28:43.725057Z 00O+Preparing environment
2026-05-08T09:28:44.369212Z 01O Running on LAPTOP-3Q7I35KD...
2026-05-08T09:28:44.489585Z 00O section_end:1778232524:prepare_script
2026-05-08T09:28:44.489585Z 00O+section_start:1778232524:get_sources
2026-05-08T09:28:44.490479Z 00O+Getting source from Git repository
2026-05-08T09:28:45.624018Z 01O Gitaly correlation ID: 01KR3EGM9XBSMYXRJBMF1K25JK
2026-05-08T09:28:45.761570Z 01O Fetching changes with git depth set to 20...
2026-05-08T09:28:45.805503Z 01O Reinitialized existing Git repository in D:/GitLab-Runner/builds/Bap6ZvsMt/0/2026seiii-110/2-1/.git/
2026-05-08T09:28:46.620607Z 01O Checking out 5f1a5b85 as detached HEAD (ref is cd)...
2026-05-08T09:28:46.707186Z 01O Removing .cache/
2026-05-08T09:28:46.827989Z 01O git-lfs/3.6.1 (GitHub; windows amd64; go 1.23.3; git ea47a34b)
2026-05-08T09:28:47.104895Z 01O 
2026-05-08T09:28:47.104895Z 01O Skipping Git submodules setup
2026-05-08T09:28:47.185090Z 00O section_end:1778232527:get_sources
2026-05-08T09:28:47.185090Z 00O+section_start:1778232527:restore_cache
2026-05-08T09:28:47.185090Z 00O+Restoring cache
2026-05-08T09:28:47.973692Z 01O Version:      18.11.1
2026-05-08T09:28:47.973692Z 01O Git revision: 5265d41d
2026-05-08T09:28:47.973692Z 01O Git branch:   18-11-stable
2026-05-08T09:28:47.973692Z 01O GO version:   go1.25.7 X:cacheprog
2026-05-08T09:28:47.973692Z 01O Built:        2026-04-20T14:49:28Z
2026-05-08T09:28:47.973692Z 01O OS/Arch:      windows/amd64
2026-05-08T09:28:47.981814Z 01O Checking cache for cd-5-non_protected...
2026-05-08T09:28:48.045186Z 01E Runtime platform                                    arch=amd64 os=windows pid=17816 revision=5265d41d version=18.11.1
2026-05-08T09:28:48.045186Z 01E No URL provided, cache will not be downloaded from shared cache server. Instead a local version of cache will be extracted. 
2026-05-08T09:28:48.074871Z 01O Successfully extracted cache
2026-05-08T09:28:48.158399Z 00O section_end:1778232528:restore_cache
2026-05-08T09:28:48.158399Z 00O+section_start:1778232528:step_script
2026-05-08T09:28:48.158399Z 00O+Executing "step_script" stage of the job script
2026-05-08T09:28:48.934717Z 01O $ pip install --upgrade pip
2026-05-08T09:28:49.430835Z 01O Requirement already satisfied: pip in C:\Users\YM\miniconda3\Lib\site-packages (26.0.1)
2026-05-08T09:28:49.794719Z 01O Collecting pip
2026-05-08T09:28:51.017756Z 01O   Downloading pip-26.1.1-py3-none-any.whl.metadata (4.6 kB)
2026-05-08T09:28:51.128368Z 01O Downloading pip-26.1.1-py3-none-any.whl (1.8 MB)
2026-05-08T09:28:56.470716Z 01O    ---------------------------------------- 1.8/1.8 MB 325.7 kB/s  0:00:05
2026-05-08T09:28:56.523082Z 01E ERROR: To modify pip, please run the following command:
2026-05-08T09:28:56.523082Z 01E C:\Users\YM\miniconda3\python.exe -m pip install --upgrade pip
2026-05-08T09:28:56.669274Z 00O section_end:1778232536:step_script
2026-05-08T09:28:56.669634Z 00O+section_start:1778232536:upload_artifacts_on_failure
2026-05-08T09:28:56.669634Z 00O+Uploading artifacts for failed job
2026-05-08T09:28:57.446403Z 01O Version:      18.11.1
2026-05-08T09:28:57.446403Z 01O Git revision: 5265d41d
2026-05-08T09:28:57.446403Z 01O Git branch:   18-11-stable
2026-05-08T09:28:57.446403Z 01O GO version:   go1.25.7 X:cacheprog
2026-05-08T09:28:57.446403Z 01O Built:        2026-04-20T14:49:28Z
2026-05-08T09:28:57.446403Z 01O OS/Arch:      windows/amd64
2026-05-08T09:28:57.454999Z 01O Uploading artifacts...
2026-05-08T09:28:57.513127Z 01E Runtime platform                                    arch=amd64 os=windows pid=14952 revision=5265d41d version=18.11.1
2026-05-08T09:28:57.513127Z 01E WARNING: junit.eval.xml: no matching files. Ensure that the artifact path is relative to the working directory (D:\GitLab-Runner\builds\Bap6ZvsMt\0\2026seiii-110\2-1) 
2026-05-08T09:28:57.513127Z 01E ERROR: No files to upload                          
2026-05-08T09:28:57.597851Z 00O section_end:1778232537:upload_artifacts_on_failure
2026-05-08T09:28:57.597851Z 00O+section_start:1778232537:cleanup_file_variables
2026-05-08T09:28:57.597851Z 00O+Cleaning up project directory and file based variables
2026-05-08T09:28:58.424825Z 00O section_end:1778232538:cleanup_file_variables
2026-05-08T09:28:58.424825Z 00O+
2026-05-08T09:28:58.424825Z 00O ERROR: Job failed: exit status 1