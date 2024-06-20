const rackDropdown = document.getElementById("supply-rack");
const voltageDropdown = document.getElementById("supply-voltage");
const crateField = document.getElementById("baseline-crate");
const triggerDropdown = document.getElementById("baseline-trigger");
const flippyVoltage = document.getElementById("supply-flippy");
const MTCDVoltage = document.getElementById("mtcd");
const defaultVoltage = document.getElementById("default-voltage");
const supplyRadio = document.getElementById("supply");
const baselineRadio = document.getElementById("baseline");

rackDropdown.onchange = function(){
    supplyRadio.checked = true;
    if (rackDropdown.value == "timing") {
        flippyVoltage.value = "6";
        flippyVoltage.innerHTML = "6V"
        MTCDVoltage.removeAttribute("hidden")
    }
    else {
        flippyVoltage.value = "8";
        flippyVoltage.innerHTML = "8V"
        if (voltageDropdown.value == "mtcd") {
            voltageDropdown.selectedIndex = 0;
        }
        MTCDVoltage.setAttribute("hidden")
    }
}

voltageDropdown.onchange = function(){
    supplyRadio.checked = true;
}

crateField.onchange = function(){
    baselineRadio.checked = true;
}

triggerDropdown.onchange = function(){
    baselineRadio.checked = true;
}