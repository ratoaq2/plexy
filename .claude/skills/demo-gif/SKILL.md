---
name: demo-gif
description: Record the README terminal demo docs/images/demo.gif with VHS, on a real Plex server. Use to make or update the demo GIF.
disable-model-invocation: true
---

# Demo GIF

`docs/images/demo.gif` shows two Plex users with different preferences. VHS records it in a container:

- `scripts/demo.tape`: the session that VHS types and records. It is the source of the current GIF.
- `scripts/demo.Dockerfile`: the plexy image, plus VHS, ttyd, and Chromium.
- `scripts/demo.sh SERVER ME FRIEND`: builds the plexy image and the VHS image, mounts the 3 configuration
  files read-only, and records.

> [!WARNING]
> The tape changes the track selection on the Plex server, for two Plex users. Get the approval of the user
> before each recording. Tell the user the titles and the changes.

## 1. Inputs

The configuration files are not in the repository. The user gives them. Do not show their content.

| Input | Mount in the container | Content |
| --- | --- | --- |
| `SERVER` | `/root/.config/plexy/config.yml` | `url`, optional `tmdb_key` |
| `ME` | `/demo/me.yml` | `token` of the first user, optional `preferences` |
| `FRIEND` | `/demo/friend.yml` | `token` of the second user, optional `preferences` |

plexy reads `SERVER` from its user configuration folder, so the GIF shows no `--url`. The `url` must work
from a container: not `localhost`.

The tape uses 2 titles and 2 scenarios: `ME` with `-l pt-BR original`, and `FRIEND` with `-l de dubbed`. The
titles must have `en`, `pt`, and `de` audio, and `pt-BR` and `de` subtitles. To find titles, search the
library with plexapi (read-only): `section.search(audioLanguage="de")`.

## 2. Hidden steps

If a user has the preference already, the visible command shows "0 movies changed". So the tape first runs
a hidden command for each user that selects the other tracks:

- `ME`: `-l de dubbed`. Do not use `-l pt-BR dubbed`: the `pt` audio does not match `pt-BR`, so plexy keeps
  the `pt-BR` subtitles, and the visible line shows no subtitle change.
- `FRIEND`: `-l de original`.

The visible commands then select the preference of each user again. The end state on the server is the
same as the start state.

## 3. Rehearse

Run the 4 commands of the tape on the host, in the tape order, with the files of the user. Before and after,
save the selected audio and subtitle stream IDs of each user and each title (plexapi, `selected`). The two
lists must be the same. If not, stop and tell the user. Show the output to the user and get the approval.

## 4. Record

1. On Windows or macOS, start the Podman machine: `podman machine start`.
2. From the repository root, run `bash scripts/demo.sh SERVER ME FRIEND`.
3. Check the stream IDs again. They must be the same as before.

Known problems that the scripts already solve:

- Debian has no `ttyd` package. `scripts/demo.Dockerfile` downloads the static binary.
- Podman on WSL: crun fails with "controller `pids` is not available". `scripts/demo.sh` adds
  `--cgroups=disabled` for Podman.
- Git Bash changes `/demo` into a Windows path. `scripts/demo.sh` sets `MSYS_NO_PATHCONV=1`.
- `Wait+Screen` finds text that is still on the screen. The tape runs `clear` between the hidden commands.

## 5. Check the frames

Save some frames as PNG, then read them:

```
uv run --no-project --with pillow python -c "
from PIL import Image
im = Image.open('docs/images/demo.gif')
n = im.n_frames
print(im.size, n, 'frames', sum((im.seek(i), im.info.get('duration', 0))[1] for i in range(n)) / 1000, 's')
for k, f in enumerate([0, n // 2, n - 1]):
    im.seek(f)
    im.convert('RGB').save(f'plans/frame{k}.png')
"
```

- The GIF must not show a URL, a token, a path, or a hidden command.
- The first command must be in the last frame. If not, increase `Set Height`.
- The GIF must be at most about 2 MB and 30 s.

Delete the PNG files when you are done. To commit, use the `ship` skill. Commit `docs/images/demo.gif` and
`scripts/demo.tape` together.
