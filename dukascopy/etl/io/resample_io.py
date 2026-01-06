class ResampleIO(BaseIO):
    def get_header(self) -> str:
        self._f_in.seek(0)
        return self._f_in.readline().decode('utf-8')

    def prepare_batch(self, header: str, batch_size: int) -> Tuple[io.StringIO, bool]:
        sio = io.StringIO()
        sio.write(f"{header.strip()},offset\n")
        
        eof = False
        for _ in range(batch_size):
            offset = self._f_in.tell()
            line_bytes = self._f_in.readline()
            if not line_bytes:
                eof = True
                break
            line = line_bytes.decode('utf-8').strip()
            sio.write(f"{line},{offset}\n")
        
        sio.seek(0)
        return sio, eof

    def commit_full_bars(self, csv_data: str, confirmed_pos: int) -> int:
        self._f_out.seek(confirmed_pos)
        self._f_out.truncate(confirmed_pos)
        self._f_out.write(csv_data)
        self._f_out.flush()
        if self.fsync:
            os.fsync(self._f_out.fileno())
        return self._f_out.tell()

    def write_trailing_bar(self, csv_data: str):
        self._f_out.write(csv_data)
        self._f_out.flush()