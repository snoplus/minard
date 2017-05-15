var chart = histogram()
    .xlabel('NHit')
    .margin({'left': 50})
    .bins(100)
    .min_bin_width(1);

function n16_pos(selector){
    $.getJSON($SCRIPT_ROOT + '/query', {'name': 'n16pos'}, function(reply){
    document.getElementById(selector).innerHTML = "N16 Source Position &emsp; X: " + Math.round(reply.values[0] * 10) / 10 + "mm &emsp; Y: " + Math.round(reply.values[1] * 10) / 10 + "mm &emsp; Z: " + Math.round(reply.values[2] * 10) / 10 + "mm";
    });	
    setTimeout(function() { n16_pos(selector); }, 1000);
}	

function n16_stat(selector){
    $.getJSON($SCRIPT_ROOT + '/query', {'name': 'n16stat'}, function(reply){
    document.getElementById(selector).innerHTML = "Simulation Mean NHit: " + reply.values.toFixed(2);
    });
    setTimeout(function() { n16_stat(selector); }, 1000);
}    

function n16_nhit(selector){
    $.getJSON($SCRIPT_ROOT + '/query', {'name': 'n16'}, function(reply){
	d3.select(selector).datum(reply.values).call(chart);
    });
    setTimeout(function() { n16_nhit(selector); }, 1000);
}

function update_chart(selector, seconds, update) {
    $.getJSON($SCRIPT_ROOT + '/query', {'name': 'nhit', 'seconds': seconds}, function(reply) {
        d3.select(selector).datum(reply.value).call(chart);
    });
    setTimeout(function() { update_chart(selector, seconds, update); }, update*1000);
}
