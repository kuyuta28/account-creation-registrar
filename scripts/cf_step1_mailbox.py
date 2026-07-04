import sys
from pathlib import Path
ROOT = Path(r'D:\\business\\account-creation')
sys.path.insert(0, str(ROOT / 'registrar' / 'src'))
sys.path.insert(0, str(ROOT / 'common' / 'src'))
print('sys.path inserted')
import asyncio
from config.settings import load_config
from mail.client import create_mailbox
async def main():
    print('loading config')
    cfg = load_config()
    print('config loaded')
    providers = cfg.mail.providers_for('cloudflare')
    print(f'providers count {len(providers)}')
    box = await create_mailbox(providers, log_fn=print)
    print(f'mailbox: {box.email} provider={box.provider}')
asyncio.run(main())
