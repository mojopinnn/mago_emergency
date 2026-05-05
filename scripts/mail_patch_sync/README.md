# Daou mail git patch sync

This utility moves git patches through Daou Office mail so a home PC can send
changes into a closed company network without `git pull`.

## Flow

```text
Home repo
  sender.py watches local git changes
  -> creates change_*.patch with git diff --binary HEAD --
  -> sends the patch to Daou Office mail

Company repo
  receiver.py reads unread Daou mail
  -> checks sender, subject prefix, token, and SHA256
  -> runs git apply --check
  -> backs up changed files
  -> runs git apply
  -> runs optional test commands
```

## First run

Run each script once to create a config file.

```bash
python scripts/mail_patch_sync/sender.py
python scripts/mail_patch_sync/receiver.py
```

Edit the generated config files before running again.

## Sender config

`sender_config.json`

```json
{
  "repo_path": "/path/to/home/repo",
  "outbox_dir": "/path/to/home/repo/.mail_patch_outbox",
  "poll_seconds": 3,
  "debounce_seconds": 2,
  "send_on_start": false,
  "exclude_globs": [
    "sender_config.json",
    "receiver_config.json",
    ".mail_patch_*",
    ".mail_patch_*/**"
  ],
  "smtp_host": "smtp.daouoffice.com",
  "smtp_port": 465,
  "smtp_security": "ssl",
  "username": "home-or-company-account@example.com",
  "password": "mail-or-app-password",
  "from_addr": "home-or-company-account@example.com",
  "to_addr": "company-receiver@example.com",
  "subject_prefix": "[MAGO-PATCH]",
  "secret_token": "replace-with-a-long-random-token"
}
```

## Receiver config

`receiver_config.json`

```json
{
  "repo_path": "D:/company/nuke-tool",
  "inbox_dir": "D:/company/nuke-tool/.mail_patch_inbox",
  "backup_dir": "D:/company/nuke-tool/.mail_patch_backups",
  "log_dir": "D:/company/nuke-tool/.mail_patch_logs",
  "poll_interval_seconds": 5,
  "imap_host": "imap.daouoffice.com",
  "imap_port": 993,
  "imap_ssl": true,
  "mailbox": "INBOX",
  "username": "company-receiver@example.com",
  "password": "mail-or-app-password",
  "allowed_sender": "home-or-company-account@example.com",
  "subject_prefix": "[MAGO-PATCH]",
  "secret_token": "replace-with-the-same-long-random-token",
  "test_commands": [
    "python main.py --smoke-test"
  ],
  "command_timeout_seconds": 300
}
```

## Daou Office notes

- Use `smtp.daouoffice.com` for outgoing mail.
- Use `imap.daouoffice.com` for IMAP on Daou Office 4.0.
- Some companies block external mail clients. If login fails, ask the mail admin
  whether SMTP/IMAP and app passwords are allowed for the account.

## Manual test without mail

Home side:

```bash
git diff --binary HEAD -- > change.patch
```

Company side:

```bash
git apply --check change.patch
git apply change.patch
python main.py --smoke-test
```

## Safety rules

- Keep home and company repos on the same base commit whenever possible.
- Use a long random `secret_token`.
- Keep `sender_config.json`, `receiver_config.json`, outbox, inbox, backups, and logs
  outside the repo or ignored by git.
- Use a dedicated receiver mailbox if the company allows it.
- Let `git apply --check` fail instead of forcing stale patches.
- Commit successful changes to the company Git server after internal testing.
