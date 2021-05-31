import json
import datetime
import pyodbc
import uuid


class AppLogger:
    def __init__(self):
        # constructor
        f = open("config.json", "rt+")
        self.dbconfig = json.load(f)
        f.close()
        self.instanceId = str(uuid.uuid4()).upper()
        self.connection_string = 'DRIVER={ODBC Driver 17 for SQL Server};' \
                                 'SERVER=' + self.dbconfig["MSSqlServer"] + ';' \
                                 'DATABASE=' + self.dbconfig["MSSqlServerDB"] + ';' \
                                 'UID=' + self.dbconfig["MSSqlUser"] + ';' \
                                 'PWD=' + self.dbconfig["MSSqlPassword"]
        pass

    def log_event(self, severity, message, video_id, video_name, channel_id, channel_name):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = pyodbc.connect(self.connection_string)
        insert_sql = 'INSERT INTO TV_TIME_FEED_LOGS ' \
                     '(INSERT_DTTM, INSTANCE_ID, SEVERITY, LOG_MESSAGE, VIDEO_ID, ' \
                     'VIDEO_NAME, CHANNEL_ID, CHANNEL_NAME)' \
                     'VALUES ( ?, ?, ?, ?, ?, ?, ?, ? ) ; '
        cur = conn.cursor()
        cur.execute(insert_sql, timestamp, self.instanceId, severity, message, video_id, video_name, channel_id,
                    channel_name)
        cur.commit()
        conn.close()

    def info(self, message, video_id=None, video_name=None, channel_id=None, channel_name=None):
        self.log_event("Info", message, video_id, video_name, channel_id, channel_name)

    def warn(self, message, video_id=None, video_name=None, channel_id=None, channel_name=None):
        self.log_event("Warning", message, video_id, video_name, channel_id, channel_name)

    def error(self, message, video_id=None, video_name=None, channel_id=None, channel_name=None):
        self.log_event("Error", message, video_id, video_name, channel_id, channel_name)

    def clean_logs(self):
        # deletes log entries older than 60 days
        sql = "exec sp_TV_TIME_LOGS_CLEANUP_60_DAYS ; "
        conn2 = pyodbc.connect(self.connection_string)
        cur2 = conn2.cursor()
        try:
            cur2.execute(sql)
            cur2.commit()
        except pyodbc.Error as e:
            print("MS SQL Error - " + str(e))
            self.error("MS SQL Error - " + str(e))
        conn2.close()
        self.info("Executed stored proc sp_TV_TIME_LOGS_CLEANUP_60_DAYS")
