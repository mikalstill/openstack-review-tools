var chart;
var allusers = [];
var responsepos = 0;
xmlhttp = new XMLHttpRequest();

$(function () {
    $(document).ready(function() {
        Highcharts.setOptions({
            global: {
                useUTC: false
            }
        });
    });
});

function GenerateChart(style, title, data) {
    chart = new Highcharts.Chart({
        chart: {
            renderTo: 'container',
            type: style,
            marginRight: 10,
        },
        title: {
            text: title,
        },
        xAxis: {
            type: 'datetime',
            tickPixelInterval: 150
        },
        yAxis: {
            title: {
                text: 'Reviews'
            },
        },
        tooltip: {
            formatter: function() {
                    return '<b>'+ this.series.name +'</b><br/>'+
                    Highcharts.dateFormat('%Y-%m-%d', this.x) +'<br/>'+
                    Highcharts.numberFormat(this.y, 2);
            }
        },
        legend: {
            enabled: true
        },
        exporting: {
            enabled: false
        },
        series: data
    });
}


function HandleClick() {
  var selected_list = [];
  var selected = "";

  for(i = 0; i < allusers.length; i++) {
    if (document.getElementById("reviewer-" + allusers[i]).checked) {
      selected_list.push(allusers[i].replace("+", "%2B"));
    }
  }
  selected = selected_list.join("+");

  project = "__total__"

  console.log("New HTTP request: " + selected);
  xmlhttp.abort();
  
  xmlhttp = new XMLHttpRequest();
  xmlhttp.onreadystatechange = StateEngine;
  responsepos = 0;

  var url = "http://openstack.stillhq.com/reviews/" + datafeed + ".cgi?reviewers=" + selected + "&project=" + project;
  console.log("Fetching " + url);
  xmlhttp.open("GET", url, true);
  xmlhttp.send();

  console.log("Request sent");
  window.location.search = "?reviewers=" + selected + "&project=" + project;
}

function SetGroup(name) {
  for(i = 0; i < allusers.length; i++) {
    document.getElementById("reviewer-" + allusers[i]).checked = false;
  }

  for(i = 0; i < groups[name].length; i++) {
    console.log("Selecting: " + groups[name][i]);
    try {
      document.getElementById("reviewer-" + groups[name][i]).checked = true;
    }
    catch (err) {
      console.log("Error: " + err);
    }
  }

  HandleClick();
}

function AddPoint(user, time, value) {
  var day = new Date(time).getTime();
  for (i = 0; i < chart.series.length; i++) {
    if (chart.series[i].name == user) {
      var handled = false;
      for (j = 0; j < chart.series[i].data.length; j++) {
        if (chart.series[i].data[j].x == day) {
          var point = chart.series[i].data[j];
          point.update(value, true, true);
          handled = true;
        }
      }

      if (!handled) {
        console.log("Added point to " + user + " series");
        chart.series[i].addPoint([day, value], true, true);
      }
    }
  }
}

var xmlhttp;
var newbody = "";

var users = [];
var usercheckboxes = "";
var groups = {};
var initial = {};

function StateEngine() {
    console.log("State engine sees ready state " + xmlhttp.readyState);

    if (xmlhttp.readyState == 3) {
      try {
        newdata = xmlhttp.responseText.substr(responsepos);
        newline = newdata.indexOf('\n');

        while (newline > -1 ) {
          packetjson = newdata.substr(0, newline);
          packet = JSON.parse(packetjson);
          console.log(packet);

          // Decode packet
          switch(packet.type) {
            case "groups":
              groups = {'clear': []};
              var groupbuttons = "<button type=button onclick='SetGroup(\"clear\");'>clear</button>";
              for (i=0; i < packet.payload.length; i++) {
                var groupname = packet.payload[i][0];
                groupbuttons = groupbuttons + "<button type=button onclick='SetGroup(\"" + groupname + "\");'>" + groupname + "</button>";
                groups[groupname] = packet.payload[i][1];
              }
              document.getElementById('groups').innerHTML = groupbuttons;
              break;

            case "users-all":
              allusers = [];
              usercheckboxes = "";
              for (i=0; i < packet.payload.length; i++) {
                var username = packet.payload[i][0];
                usercheckboxes = usercheckboxes + "<input type=checkbox id=reviewer-" + username + " onclick=\"HandleClick();\">" + username + " ";
                allusers.push(username);
              }
              document.getElementById('reviewers').innerHTML = usercheckboxes;
              break;

            case "users-present":
              for (i=0; i < packet.payload.length; i++) {
                console.log("Create user: " + packet.payload[i])
                initial[packet.payload[i]] = [];
                try {
                  document.getElementById("reviewer-" + packet.payload[i]).checked = true;
                }
                catch (err) {
                  console.log("Error: " + err);
                }
              }
              users = packet.payload;
              break;

            case "initial-value":
              console.log("Initial entry: " + packet.user + ", " + packet.day + ", " + packet.payload);
              var day = new Date(packet.day);
              initial[packet.user].push([day.getTime(), packet.payload]);
              break;

            case "initial-value-ends":
              console.log("Draw graph");

              var series = [];
              for (i=0; i < users.length; i++) {
                series.push({'name': users[i],
                             'data': initial[users[i]]})
              }

              GenerateChart(graphstyle, graphtitle, series);
              break;

            case "update-value":
              console.log("Update user entry: " + packet.user + ", " + packet.day + ", " + packet.payload);
              AddPoint(packet.user, packet.day, packet.payload);
              break;

            case "keepalive":
              console.log("Connection still alive");
              break;

            case "debug":
              console.log("From server: " + packet.payload);
              break;

            default:
              console.log("Unknown packet!");
              console.log(packet);
              break;
          }

          newdata = newdata.substr(newline + 1);
          responsepos = responsepos + newline + 1;
          newline = newdata.indexOf('\n');
        }
      }
      catch(err) {
        console.log("Error: " + err);
      }
    }
    else {
      xmlhttp.onreadystatechange = StateEngine;
    }
}

// Get URL param
var params = window.location.search;
console.log("Calling params are " + params);

xmlhttp.onreadystatechange = StateEngine;
var url = "http://openstack.stillhq.com/reviews/" + datafeed + ".cgi" + params;
console.log("Fetching " + url);
xmlhttp.open("GET", url, true);
xmlhttp.send();
