from ftplib import FTP

ftp_session = FTP("ftp.wisepower.it", "1451303@aruba.it", "QWEasz123*", timeout=60)
ftp_session.cwd("www.wisepower.it/ws_iot")

stored_files = ftp_session.nlst()[2:]
for f in stored_files:
    if f == "config.txt":
        with open(f, "w") as fp:
            ftp_session.retrlines('RETR %s' % f, fp.writelines)
ftp_session.quit()

