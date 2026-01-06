# testing library


def get_candle_right_boundary(symbol, ts, timeframe, config):
    # determine active session for this symbol, ts, timeframe and config
    # get the origin for this ts, symbol, session and tf
    # get the dst gap regarding to reference date
    # calculate theoretical ending time (A) of this candle in server-time, limit by session-end
    # if merge steps were defined, determine to which session the candle with
    # ends_with belongs. Can do this using the sessions "grid"
    # calculate the length of the candle that was actually merged (B) 
    # calculate the total length of the combined candle (A+B)
    # add the total length in minutes to the start of this candle (C)
    # HEY! we have the right boundary (ts+C)!
    # something like this yes!
    # shouldnt be even too hard of a performance impact :)
    pass