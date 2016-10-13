/**
 * Called by edX to initialize the xblock.
 * @param runtime - provided by EdX
 * @param element - provided by EdX
 */
function Initialize_CTATXBlock(runtime,element) 
{
	var JSONDriver=new X2JS(); // Included library originally obtained at: https://github.com/abdmob/x2js
    var post = {
	save_problem_state: function(state) {
	    $.ajax({
		type: "POST",
		url: runtime.handlerUrl(element, 'ctat_save_problem_state'),
		data: JSON.stringify({state:state}),
		contentType: "application/json; charset=utf-8",
		dataType: "json"});
	},
	get_problem_state: function() {
	    return $.ajax({
		type: "POST",
		url: runtime.handlerUrl(element, 'ctat_get_problem_state'),
		data: JSON.stringify({}),
		contentType: "application/json; charset=utf-8",
		dataType: "json"});
	},
	report_grade: function(correct_step_count, total_step_count) {
	    $.ajax({
		type: "POST",
		url: runtime.handlerUrl(element, 'ctat_grade'),
		data: JSON.stringify({'value': correct_step_count,
				      'max_value': total_step_count}),
		contentType: "application/json; charset=utf-8",
		dataType: "json"});
	},
	log_event: function(aMessage) 
	{				
	    $.ajax(
		{
			type: "POST",
			url: runtime.handlerUrl(element, 'ctat_log'),
			data: JSON.stringify({'event_type':'ctat_log',
								  'action':'CTATlogevent',
								  'problem_name' : CTATConfig.problem_name,
								  'dataset_name' : CTATConfig.dataset_name,								  
								  'message': JSONDriver.xml_str2json (aMessage)}),
			contentType: "application/json; charset=utf-8",
			dataType: "json"
	    });
	}
    };
    $('.stattutor').on("load", function() {
	this.contentWindow.CTATTarget = "XBlock"; // needed for ctatloader.js
	var lms = this.contentWindow.CTATLMS;
	lms.identifier = 'XBlock';
	lms.setValue = function(key,value) {
	    CTATConfig[key]=value;
	};
	lms.getValue = function(key) { return CTATConfig[key]; };
	lms.saveProblemState = function (state) {
	    post.save_problem_state(window.btoa(state.problem_state));
	};
	lms.getProblemState = function (handler) {
	    post.get_problem_state().done(function(data) {
		return handler(window.atob(data.state)); });
	};
	lms.gradeStudent = function (correct_step_count, total_step_count) {
	    post.report_grade(correct_step_count, total_step_count);
	};
	lms.logEvent = function (aMessage) {
	    post.log_event(aMessage);
	};
	// CTATConfig is from CTATConfig.js which is a template that is filled
	// out by ctatxblock.py
	this.contentWindow.initialize_stattutor(CTATConfig);
    });
};
