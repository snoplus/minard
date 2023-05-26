$("#step-menu").on("change", function() {
    window.location.replace($SCRIPT_ROOT + "/psup-temp?step=" + this.value + "&height=" + height);
});

var context = create_context('#main', step);

var CAVITY_TEMP_SENSORS = [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31
];

function metric(name) {
    var display = name;

    // display 20LB trigger as 20L
    if (name == "20LB") {
        display = "20L";
    } else if (name == "20LB-Baseline") {
        display = "20L-Baseline";
    } else if (name == "EXT6") {
        display = "NO CLOCK";
    }

    return context.metric(function(start, stop, step, callback) {
        d3.json($SCRIPT_ROOT + '/metric' + 
                '?expr=' + name +
                '&start=' + start.toISOString() +
                '&stop=' + stop.toISOString() +
                '&now=' + new Date().toISOString() +
                '&step=' + Math.floor(step/1000), function(data) {
                if (!data) return callback(new Error('unable to load data'));
                return callback(null,data.values);
        });
    }, display);
}

function add_horizon(expressions, format, colors, extent, offset) {
    var horizon = context.horizon().height(Number(height));

    if (typeof format != "undefined") horizon = horizon.format(format);
    if (typeof colors != "undefined" && colors) horizon = horizon.colors(colors);
    if (typeof extent != "undefined") horizon = horizon.extent(extent);
    if (typeof offset != "undefined") horizon = horizon.offset(offset);

    d3.select('#main').selectAll('.horizon')
        .data(expressions.map(metric), String)
      .enter().insert('div','.bottom')
        .attr('class', 'horizon')
        .call(horizon)
        .on('click', function(d, i) {
            var domain = context.scale.domain();
            var params = {
                name: expressions[i],
                start: domain[0].toISOString(),
                stop: domain[domain.length-1].toISOString(),
                step: Math.floor(context.step()/1000)
            };
            window.open($SCRIPT_ROOT + "/graph?" + $.param(params), '_self');
        });
}

add_horizon(CAVITY_TEMP_SENSORS.map(function(x) { return "temp-" + x; }),
            format_rate,
            null,
            [-5,5],
            -15);

context.on("focus", function(i) {
  d3.selectAll(".value").style("right", i === null ? null : context.size() - i + "px");
});
