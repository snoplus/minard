function create_context(target) {
    var scale = tzscale().zone('America/Toronto');

    var size = $(target).width();
    var context = cubism.context(scale)
        .serverDelay(2e3)
        .clientDelay(1e3)
        .step(5e3)
        .size(size);

    function format_seconds(date) {
        return moment.tz(date, 'America/Toronto').format('hh:mm:ss');
    }

    function format_minutes(date) {
        return moment.tz(date, 'America/Toronto').format('hh:mm');
    }

    function format_day(date) {
        return moment.tz(date, 'America/Toronto').format('MMMM DD');
    }

    if (context.step() < 6e4) {
        focus_format = format_seconds;
    } else if (context.step() < 864e5) {
        focus_format = format_minutes;
    } else {
        focus_format = format_day;
    }

    // delete old axes
    $(target + ' .axis').remove();

    // add time axes
    d3.select(target).selectAll(".axis")
        .data(["top", "bottom"])
      .enter().append("div")
        .attr("class", function(d) { return d + " axis"; })
        .each(function(d) {
            var axis = context.axis()
                .ticks(12)
                .orient(d)
                .focusFormat(focus_format)
            d3.select(this).call(axis);
        });

    // delete old rule
    $(target + ' .rule').remove();

    d3.select(target).append("div")
        .attr("class", "rule")
        .call(context.rule());

    return context;
}

function metric(timeseries, crate, card, channel) {
    var label;
    if (card === null)
        label = 'crate ' + crate;
    else if (channel == null)
        label = 'card ' + card;
    else
        label = 'channel ' + channel;

    return timeseries.context.metric(function(start, stop, step, callback) {
        var params = {
            name: timeseries.source,
            start: start.toISOString(),
            stop: stop.toISOString(),
            now: new Date().toISOString(),
            step: 5,
            crate: crate,
            card: card,
            channel: channel,
            method: timeseries.method
        }

        d3.json($SCRIPT_ROOT + '/metric_hash?' + $.param(params),
            function(data) {
                if (!data)
                    return callback(new Error('unable to load data'));

                return callback(null,data.values);
            }
        );
    }, label);
}

function draw(timeseries) {
    // create a horizon from timeseries.context and draw horizons
    if (timeseries.horizon) {
        d3.select(timeseries.target).selectAll('.horizon')
        .call(timeseries.horizon.remove)
        .remove();
    }

    timeseries.horizon = timeseries.context.horizon()
        .height(20)
        .colors(timeseries.scale.range().concat(timeseries.scale.range()))
        .extent(timeseries.scale.domain())
        .format(timeseries.format);

    var horizons = d3.select(timeseries.target).selectAll('.horizon')
        .data(timeseries.metrics)
      .enter().insert('div','.bottom')
          .attr('class', 'horizon')
          .call(timeseries.horizon);

    if (timeseries.click)
        horizons.on('click', timeseries.click);
}

function update_metrics(timeseries) {
    if (timeseries.context != null)
        timeseries.context.stop();

    timeseries.context = create_context(timeseries.target);
    timeseries.metrics = [];

    if (typeof timeseries.crate === 'undefined') {
        for (var i=0; i < 19; i++)
            timeseries.metrics[i] = metric(timeseries, i, null, null);
    } else if (typeof timeseries.card === 'undefined') {
        for (var i=0; i < 16; i++)
            timeseries.metrics[i] = metric(timeseries, timeseries.crate, i, null);
    } else {
        for (var i=0; i < 32; i++)
            timeseries.metrics[i] = metric(timeseries, timeseries.crate, timeseries.card, i);
    }
}

si_format = d3.format('.2s');

function format(d) {
    if (d == null)
        return '-';
    else
        return si_format(d);
}

var default_thresholds = {
    cmos: [100,2e3],
    base: [10, 80],
    occupancy: [0.001, 0.002]
}

function set_thresholds(lo, hi) {
    // set thresholds text area
    $('#threshold-lo').val(lo)
    $('#threshold-hi').val(hi)
}

function switch_to_crate(crate) {
    card.crate(crate);
    d3.select('#card').call(card);

    blah.crate = crate;
    blah.state = NEEDS_UPDATE;
    channelts.crate = crate;
    channelts.state = NEEDS_UPDATE;

    $('.carousel').carousel('next');
}

function switch_to_channel(crate, card) {
    channelts.crate = crate;
    channelts.card = card;
    channelts.state = NEEDS_UPDATE;
    $('#carousel').carousel('next');
}

var ACTIVE = 0,
    PAUSED = 1,
    NEEDS_UPDATE = 2;

var spam = {
target: '#timeseries',
source: $('#data-source').val(),
method: $('#data-method').val(),
context: null,
horizon: null,
scale: null,
metrics:null,
format: format,
click: function(d, i) {
    switch_to_crate(i);
    },
state: NEEDS_UPDATE,
slide: 0
}
    
var blah = {
target: '#timeseries-card',
source: $('#data-source').val(),
method: $('#data-method').val(),
context: null,
horizon: null,
scale: null,
metrics:null,
format: format,
crate: 0,
click: function(d, i) {
    switch_to_channel(blah.crate, i);
    },
state: NEEDS_UPDATE,
slide: 1
}
    
var channelts = {
target: '#timeseries-channel',
source: $('#data-source').val(),
method: $('#data-method').val(),
context: null,
horizon: null,
scale: null,
metrics:null,
format: format,
crate: 0,
card: 0,
state: NEEDS_UPDATE,
slide: 2
}

function setup() {
    source = $('#data-source').val();
    method = $('#data-method').val();

    var thresholds = default_thresholds[source];

    scale = d3.scale.threshold()
        .domain(thresholds)
        .range(colorbrewer['YlOrRd'][3]);

    spam.scale = scale;
    update_metrics(spam);
    draw(spam);
    spam.state = ACTIVE;

    blah.scale = scale;
    channelts.scale = scale;

    // set default thresholds in text area
    $('#threshold-lo').val(thresholds[0])
    $('#threshold-hi').val(thresholds[1])

    card = card_view()
        .scale(scale);

    crate = crate_view()
        .scale(scale)
        .click(function(d, i) {
            switch_to_crate(i);
        });

    if (source == 'cmos') {
        card.format(d3.format('.2s'));
    } else if (source == "occupancy") {
        card.format(d3.format('.0e'));
    } else {
        card.format(d3.format());
    }
}

setup();

var timeseries = [spam, blah, channelts];

function update_state(call_update_metric) {
    call_update_metric = typeof call_update_metric === 'undefined' ? true : false;

    timeseries.forEach(function(ts) {
        switch (ts.state) {
            case ACTIVE:
                if (call_update_metric)
                    update_metrics(ts);
                draw(ts);
                break;
            case PAUSED:
                if (call_update_metric)
                    ts.state = NEEDS_UPDATE;
                else
                    draw(ts);
        }
    });
}

$('#data-method').change(function() {
    spam.method = this.value;
    blah.method = this.value;
    channelts.method = this.value;

    update_state();
});

$('#data-source').change(function() {
    if (this.value == 'cmos') {
        card.format(d3.format('.2s'));
    } else if (this.value == "occupancy") {
        card.format(d3.format('.0e'));
    } else {
        card.format(d3.format());
    }

    // update threshold values
    var thresholds = default_thresholds[this.value];
    set_thresholds.apply(this,thresholds);
    // update color scale
    scale.domain(thresholds);
    update();

    // update source, scale, and redraw
    spam.source = this.value;
    spam.scale.domain(thresholds);
    blah.source = this.value;
    blah.scale.domain(thresholds);
    channelts.source = this.value;
    channelts.scale.domain(thresholds);

    update_state();
});

$('#threshold-lo').keypress(function(e) {
    if (e.which == 13) {
        spam.scale.domain([this.value,scale.domain()[1]]);
        blah.scale.domain([this.value,scale.domain()[1]]);

        update_state(false);

        d3.select("#crate").call(crate);
        d3.select("#card").call(card);
    }
});

$('#threshold-hi').keypress(function(e) {
    if (e.which == 13) {
        spam.scale.domain([scale.domain()[0],this.value]);
        blah.scale.domain([scale.domain()[0],this.value]);

        update_state(false);

        d3.select("#crate").call(crate);
        d3.select("#card").call(card);
    }
});

$('.carousel').on('slid.bs.carousel', function(e) {
    var slide = $(e.relatedTarget).index();
    $('#card-heading').text('Crate ' + blah.crate);
    $('#channel-heading').text('Crate ' + channelts.crate + ', Card ' + channelts.card);

    timeseries.forEach(function(ts) {
        if (ts.slide == slide) {
            if (ts.state == NEEDS_UPDATE) {
                update_metrics(ts);
                draw(ts);
                ts.state = ACTIVE;
            } else if (ts.state == PAUSED) {
                ts.context.start();
                ts.state = ACTIVE;
            } else {
                console.log('timeseries already active');
            }
        } else {
            if (ts.state == ACTIVE) {
                ts.context.stop();
                ts.state = PAUSED;
            }
        }
    });
});

var interval = 5000;

function update() {
    var name = $('#data-source').val();
    $.getJSON($SCRIPT_ROOT + '/query', {name: name, stats: $('#stats').val()})
        .done(function(result) {
            d3.select('#crate').datum(result.values).call(crate);
            d3.select('#card').datum(result.values).call(card);
        });
}

d3.select('#crate').datum([]).call(crate);
d3.select('#card').datum([]).call(card);
// wrap first ten and last ten crates in a div
$('#crate' + [0,1,2,3,4,5,6,7,8,9].join(',#crate')).wrapAll('<div />');
$('#crate' + [10,11,12,13,14,15,16,17,18,19].join(',#crate')).wrapAll('<div />');
update();
setInterval(update,interval);
