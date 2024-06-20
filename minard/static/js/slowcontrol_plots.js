const rackDropdown = document.getElementById("supply-rack");
const voltageDropdown = document.getElementById("supply-voltage");
const flippyVoltage = document.getElementById("supply-flippy");

rackDropdown.onchange = function(){
    if (rackDropdown.value == "timing") {
        flippyVoltage.value = "6";
        flippyVoltage.innerHTML = "6V"
    }
    else {
        flippyVoltage.value = "8";
        flippyVoltage.innerHTML = "8V"
    }
}