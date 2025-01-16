import os
import logging
from datetime import datetime
import subprocess
from flask import current_app
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DatabaseBackup:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        self.backup_dir = os.path.join(os.getcwd(), 'backups')
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def create_backup(self):
        """Create a backup of the database"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(self.backup_dir, f'backup_{timestamp}.sql')

            # Parse database URL
            db_params = self._parse_db_url()

            # Create backup using pg_dump with SSL mode
            command = [
                'pg_dump',
                '-h', db_params['host'],
                '-p', db_params['port'],
                '-U', db_params['user'],
                '-d', db_params['dbname'],
                '--no-owner',  # Exclude ownership commands
                '--no-acl',    # Exclude access privileges
                '-f', backup_file
            ]

            # Add SSL mode options for secure connections
            if db_params.get('sslmode') == 'require':
                command.extend(['--no-password'])
                os.environ['PGSSLMODE'] = 'require'

            env = os.environ.copy()
            env['PGPASSWORD'] = db_params['password']

            logger.info(f"Starting database backup to {backup_file}")
            result = subprocess.run(
                command,
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Database backup created successfully: {backup_file}")

            # Keep only last 5 backups
            self._cleanup_old_backups()

            return True, backup_file
        except subprocess.CalledProcessError as e:
            error_msg = f"pg_dump error: {e.stderr}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Backup creation failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _parse_db_url(self):
        """Parse database URL into components, handling SSL mode"""
        try:
            # Parse the URL
            url = self.db_url.replace('postgres://', 'postgresql://')  # Normalize protocol
            result = urlparse(url)

            # Extract query parameters
            query_params = {}
            if result.query:
                query_params = dict(param.split('=') for param in result.query.split('&'))

            # Split credentials
            if '@' in result.netloc:
                auth, host_port = result.netloc.split('@')
                user, password = auth.split(':')
            else:
                host_port = result.netloc
                user = password = ''

            # Split host and port
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host = host_port
                port = '5432'

            # Clean up the path to get database name
            dbname = result.path.lstrip('/')
            # Remove any query parameters from dbname
            if '?' in dbname:
                dbname = dbname.split('?')[0]

            params = {
                'user': user,
                'password': password,
                'host': host,
                'port': port,
                'dbname': dbname,
                'sslmode': query_params.get('sslmode', 'require')  # Default to require for Neon DB
            }

            # Validate parameters
            for key, value in params.items():
                if not value and key not in ['password']:  # Password can be empty for some setups
                    raise ValueError(f"Missing required parameter: {key}")

            return params

        except Exception as e:
            logger.error(f"Error parsing database URL: {str(e)}")
            raise

    def _cleanup_old_backups(self):
        """Keep only the 5 most recent backups"""
        try:
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.startswith('backup_')],
                reverse=True
            )

            # Remove old backups keeping only the last 5
            for old_backup in backups[5:]:
                os.remove(os.path.join(self.backup_dir, old_backup))
                logger.info(f"Removed old backup: {old_backup}")
        except Exception as e:
            logger.error(f"Cleanup of old backups failed: {str(e)}")

    @classmethod
    def schedule_backup(cls):
        """Create a new backup if it's time"""
        try:
            backup = cls()
            success, result = backup.create_backup()
            if success:
                logger.info("Scheduled backup completed successfully")
            else:
                logger.error(f"Scheduled backup failed: {result}")
        except Exception as e:
            logger.error(f"Scheduled backup error: {str(e)}")