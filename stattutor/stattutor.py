"""
This is a XBlock used to serve the CTAT based StatTutor problems originally
implemented for OLI (http://oli.cmu.edu/).
"""

import re
import uuid
import pkg_resources
import base64

# pylint: disable=import-error
# The xblock packages are available in the runtime environment.
from xblock.core import XBlock
from xblock.fields import Scope, Integer, String, Float, Boolean
from xblock.fragment import Fragment
# pylint: enable=import-error


class StattutorXBlock(XBlock):
    """
    A XBlock providing a CTAT backed StatTutor.
    """
    # pylint: disable=too-many-instance-attributes
    # All of the instance variables are required.

    display_name = String(
        help="Display name of the component",
        default="StatTutor",
        scope=Scope.content) # required to prevent garbage name at the top

    # **** xBlock tag variables ****
    # The width must be at least 900 in order to accommodate some dynamically
    # loaded images and some of the interactive elements without causing
    # side scrolling scrollbars to appear.  They are set here instead of
    # hard coding them into ctatxblock.html to make it easier for EdX
    # administrators to modify them if they wish without having to scour
    # all of the code for where they are set.
    width = 900 # Width of the StatTutor frame.
    height = 750 # Height of the StatTutor frame.

    # **** Grading variables ****
    # All of the variable in this section are required to get grading to work
    # according to EdX's documentation.
    has_score = Boolean(default=True, scope=Scope.content)
    icon_class = String(default="problem", scope=Scope.content)
    score = Integer(help="Current count of correctly completed student steps",
                    scope=Scope.user_state, default=0)
    max_problem_steps = Integer(
        help="Total number of steps",
        scope=Scope.user_state, default=1)
    max_possible_score = 1

    def max_score(self):
        """ The maximum raw score of the problem. """
        # For some unknown reason, errors are thrown if the return value is
        # hard coded.
        return self.max_possible_score
    attempted = Boolean(help="True if at least one step has been completed",
                        scope=Scope.user_state, default=False)
    completed = Boolean(
        help="True if all of the required steps are correctly completed",
        scope=Scope.user_state, default=False)
    weight = Float(
        display_name="Problem Weight",
        help=("Defines the number of points each problem is worth. "
              "If the value is not set, the problem is worth the sum of the "
              "option point values."),
        values={"min": 0, "step": .1},
        scope=Scope.settings
    )  # weight needs to be set to something, errors will be thrown if it does
    # not exist.

    # **** Basic interface variables ****
    # All of the variable in this section are required to get the tutors to run
    src = "public/html/StatTutor.html" # this is static in StatTutor
    # src can not be hard coded into static/html/ctatxblock.html because of the
    # relative path issues discussed elsewhere in this file.

    # Generate and store a dictionary of the available problems.
    # (AKA the problem whitelist)
    problems = {}
    for d in pkg_resources.resource_listdir(__name__, 'public/problem_files/'):
        pdir = 'public/problem_files/{}'.format(d)
        if pkg_resources.resource_isdir(__name__, pdir):
            pdir_files = [f for f in
                          pkg_resources.resource_listdir(__name__, pdir)]
            brds = [brd for brd in pdir_files if '.brd' in brd]
            desc = [dsc for dsc in pdir_files if '.xml' in dsc]
            if len(brds) > 0 and len(desc) > 0:
                problems[d] = {'name': d,
                               'brd': pdir + '/' + brds[0],
                               'description': pdir + '/' + desc[0]}
    problem = String(help="The selected problem from problems",
                     default="m1_survey", scope=Scope.settings)

    # **** CTATConfiguration variables ****
    log_name = String(help="Problem name to log", default="CTATEdXProblem",
                      scope=Scope.settings)
    log_dataset = String(help="Dataset name to log", default="edxdataset",
                         scope=Scope.settings)
    log_level1 = String(help="Level name to log", default="unit1",
                        scope=Scope.settings)
    log_type1 = String(help="Level type to log", default="unit",
                       scope=Scope.settings)
    log_level2 = String(help="Level name to log", default="unit2",
                        scope=Scope.settings)
    log_type2 = String(help="Level type to log", default="unit",
                       scope=Scope.settings)
    log_url = String(help="URL of the logging service",
                     default="http://pslc-qa.andrew.cmu.edu/log/server",
                     scope=Scope.settings)
    # None, ClientToService, ClientToLogServer, or OLI
    logtype = String(help="How should data be logged",
                     default="None", scope=Scope.settings)
    log_diskdir = String(
        help="Directory for log files relative to the tutoring service",
        default=".", scope=Scope.settings)
    log_port = String(help="Port used by the tutoring service", default="8080",
                      scope=Scope.settings)
    log_remoteurl = String(
        help="Location of the tutoring service (localhost or domain name)",
        default="localhost", scope=Scope.settings)

    ctat_connection = String(help="", default="javascript",
                             scope=Scope.settings)

    # **** User Information ****
    # This section includes variables necessary for storing partial
    # student answers so that they can come back and work on a problem
    # without worrying about loosing progress.
    saveandrestore = String(help="Internal data blob used by the tracer",
                            default="", scope=Scope.user_state)

    # **** Utility functions and methods ****
    @staticmethod
    def resource_string(path):
        """ Read in the contents of a resource file. """
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    @staticmethod
    def strip_local(url):
        """ Returns the given url with //localhost:port removed. """
        return re.sub(r'//localhost(:\d*)?', '', url)

    def get_local_resource_url(self, url):
        """ Wrapper for self.runtime.local_resource_url. """
        # It has been observed that self.runtime.local_resource_url(self, url)
        # prepends "//localhost:(port)" which makes accessing the Xblock in EdX
        # from a remote machine fail completely.
        return self.strip_local(self.runtime.local_resource_url(self, url))

    # **** XBlock methods ****

    # -------------------------------------------------------------------
    # Here we construct the tutor html page from various resources. This
    # is where all things go to hell. We can't use jsrender because the
    # XBlock API call add_resource doesn't support non-registered mime-
    # types and it doesn't support the addition of an id for the script
    # tag.
    # More information on this poor excuse for an API at:
    #
    # http://edx.readthedocs.org/projects/xblock/en/latest/fragment.html
    #
    # The XBlock developers seem to be confused as to what a relative url
    # is but have no problem accusing outside developers of not
    # understanding the concept. Also of course major documentation missing
    # or unclear on how to add static resources to XBLock html pages and
    # CSS files:
    #
    # https://groups.google.com/forum/#!topic/edx-code/MXWBNkE6gjU
    #
    # -------------------------------------------------------------------

    def student_view(self, dummy_context=None):
        """
        Create a Fragment used to display a CTAT StatTutor xBlock to a student.

        Returns a Fragment object containing the HTML to display
        """
        # read in template html
        html = self.resource_string("static/html/ctatxblock.html")
        brd = self.problems[self.problem]['brd']
        description = self.problems[self.problem]['description']
        frag = Fragment(html.format(
            # Until the iframe srcdoc attribute is universally supported
            # a valid xblock generated url has to be passed into
            # ctatxblock.html.  Internet Explorer does not support srcdoc.
            tutor_html=self.get_local_resource_url(self.src),
            width=self.width, height=self.height))
        config = self.resource_string("static/js/CTATConfig.js")
        frag.add_javascript(config.format(
            self=self,
            tutor_html=self.get_local_resource_url(self.src),
            question_file="data:file/brd;base64," +
            base64.b64encode(self.resource_string(brd)),
            student_id=self.runtime.anonymous_student_id
            if hasattr(self.runtime, 'anonymous_student_id')
            else 'bogus-sdk-id',
            problem_description=self.get_local_resource_url(description),
            guid=str(uuid.uuid4())))
        frag.add_javascript(self.resource_string(
            "static/js/Initialize_CTATXBlock.js"))
        frag.initialize_js('Initialize_CTATXBlock')
        return frag

    @XBlock.json_handler
    def ctat_grade(self, data, dummy_suffix=''):
        """
        Handles updating the grade based on post request from the tutor.

        Args:
          self: the StatTutor XBlock.
          data: 
          dummy_suffix: unused but required as a XBlock.json_handler.
        Returns:
          A JSON object reporting the success or failure.
        """
        self.attempted = True
        corrects = int(data.get('value'))
        self.max_problem_steps = int(data.get('max_value'))
        # only change score if it increases.
        # this is done because corrects should only ever increase and
        # it deals with issues EdX has with grading, in particular
        # the multiple identical database entries issue.
        if corrects > self.score:
            self.score = corrects
            self.completed = self.score >= self.max_problem_steps
            scaled = float(self.score)/float(self.max_problem_steps)
            # trying with max of 1. because basing it on max_problem_steps
            # seems to cause EdX to incorrectly report the grade.
            event_data = {'value': scaled, 'max_value': 1.0}
            # pylint: disable=broad-except
            # The errors that should be checked are django errors, but there
            # type is not known at this point. This exception is designed
            # partially to learn what the possible errors are.
            try:
                self.runtime.publish(self, 'grade', event_data)
            except Exception as err:
                return {'result': 'fail', 'Error': err.message}
            return {'result': 'success', 'finished': self.completed,
                    'score': scaled}
            # pylint: enable=broad-except
        return {'result': 'no-change', 'finished': self.completed,
                'score': float(self.score)/float(self.max_problem_steps)}

    def studio_view(self, dummy_context=None):
        """ Generate the Studio page contents. """
        html = self.resource_string("static/html/ctatstudio.html")
        problem_dirs = [
            '<option value="{0}"{1}>{0}</option>'.format(
                d, ' selected' if d == self.problem else '')
            for d in self.problems.keys()]
        problem_dirs.sort()
        frag = Fragment(html.format(self=self, problems=''.join(problem_dirs)))
        studio_js = self.resource_string("static/js/ctatstudio.js")
        frag.add_javascript(unicode(studio_js))
        frag.initialize_js('CTATXBlockStudio')
        return frag

    @XBlock.json_handler
    def studio_submit(self, data, dummy_suffix=''):
        """
        Called when submitting the form in Studio.

        Args:
          self: the StatTutor XBlock.
          data: a JSON object encoding the form data from
                static/html/ctatstudio.html
          dummy_suffix: unused but required as a XBlock.json_handler.
        Returns:
          A JSON object reporting the success of the operation.
        """
        status = 'success'
        statmodule = data.get('statmodule')
        if statmodule in self.problems.keys():
            self.problem = statmodule
        else:
            status = 'failure'
        return {'result': status}

    @XBlock.json_handler
    def ctat_save_problem_state(self, data, dummy_suffix=''):
        """Called from CTATLMS.saveProblemState.
        This saves the current state of the tutor after each correct action.

        Args:
          self: the StatTutor XBlock.
          data: A JSON object with a 'state' field with a payload of the blob
                of 64 bit encoded data that represents the current
                state of the tutor.
          dummy_suffix: unused but required as a XBlock.json_handler.
        Returns:
          A JSON object with a 'result' field with a payload indicating the
          success status.
        """
        if data.get('state') is not None:
            self.saveandrestore = data.get('state')
            return {'result': 'success'}
        return {'result': 'failure'}

    @XBlock.json_handler
    def ctat_get_problem_state(self, dummy_data, dummy_suffix=''):
        """
        Return the stored problem state to reconstruct a student's progress.

        Args:
          self: the StatTutor XBlock.
          dummy_data: unused but required as a XBlock.json_handler.
          dummy_suffix: unused but required as a XBlock.json_handler.
        Returns:
          A JSON object with a 'result' and a 'state' field.
        """
        return {'result': 'success', 'state': self.saveandrestore}

    @staticmethod
    def workbench_scenarios():
        """ Prescribed XBlock method for displaying this in the workbench. """
        return [
            ("StattutorXBlock",
             """<vertical_demo>
                <stattutor width="900" height="750"/>
                </vertical_demo>
             """),
        ]
