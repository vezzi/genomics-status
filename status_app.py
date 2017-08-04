""" Main genomics-status web application.
"""
import base64
import subprocess
import uuid
import yaml
import json
import requests

from collections import OrderedDict
from couchdb import Server

import tornado.autoreload
import tornado.httpserver
import tornado.ioloop
import tornado.web

from tornado import template
from tornado.options import define, options

from status.util import BaseHandler, MainHandler
from status.flowcells import  FlowcellSearchHandler




class Application(tornado.web.Application):
    def __init__(self, settings):

        # Set up a set of globals to pass to every template
        self.gs_globals = {}

        # GENOMICS STATUS MAJOR VERSION NUMBER
        # Bump this with any change that requires an update to documentation
        self.gs_globals['gs_version'] = '1.0';

        # Get the latest git commit hash
        # This acts as a minor version number for small updates
        # It also forces javascript / CSS updates and solves caching problems
        try:
            self.gs_globals['git_commit'] = subprocess.check_output(['git', 'rev-parse', '--short=7', 'HEAD']).strip()
            self.gs_globals['git_commit_full'] = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip()
        except:
            self.gs_globals['git_commit'] = 'unknown'
            self.gs_globals['git_commit_full'] = 'unknown'

#        handlers = [
#            ("/", MainHandler),
#            (r'.*', BaseHandler),
#        ]
        handlers = [
            ("/", MainHandler),
            ("/api/v1/flowcell_search/([^/]*)$", FlowcellSearchHandler),
            (r'.*', BaseHandler)
        ]

        self.declared_handlers = handlers

        # Load templates
        self.loader = template.Loader("design")

        # Global connection to the database
        couch = Server(settings.get("couch_server", None))
        if couch:
            self.analysis_db = couch["analysis"]
            self.application_categories_db = couch["application_categories"]
            self.bioinfo_db = couch["bioinfo_analysis"]
            self.cronjobs_db = couch["cronjobs"]
            self.flowcells_db = couch["flowcells"]
            self.gs_users_db = couch["gs_users"]
            self.instruments_db= couch["instruments"]
            self.instrument_logs_db = couch["instrument_logs"]
            self.projects_db = couch["projects"]
            self.samples_db = couch["samples"]
            self.server_status_db = couch['server_status']
            self.suggestions_db = couch["suggestion_box"]
            self.worksets_db = couch["worksets"]
            self.x_flowcells_db = couch["x_flowcells"]
        else:
            print settings.get("couch_server", None)
            raise IOError("Cannot connect to couchdb");

        # Load columns and presets from genstat-defaults user in StatusDB
        genstat_id = ''
        for u in self.gs_users_db.view('authorized/users'):
            if u.get('key') == 'genstat-defaults':
                genstat_id = u.get('value')

        # It's important to check that this user exists!
        if not genstat_id:
            raise RuntimeError("genstat-defaults user not found on {}, please " \
                               "make sure that the user is abailable with the " \
                               "corresponding defaults information.".format(settings.get("couch_server", None)))

        # We need to get this database as OrderedDict, so the pv_columns doesn't
        # mess up
        user = settings.get("username", None)
        password = settings.get("password", None)
        headers = {"Accept": "application/json"}
        #           "Authorization": "Basic " + "{}:{}".format(user, password).encode('base64')[:-1]}
        decoder = json.JSONDecoder(object_pairs_hook=OrderedDict)
        user_url = "{}/gs_users/{}".format(settings.get("couch_server"), genstat_id)
        json_user = requests.get(user_url, headers=headers).content.rstrip()
        self.genstat_defaults = decoder.decode(json_user)

        # If settings states  mode, no authentication is used
        self.test_mode = settings["Testing mode"]

        # google oauth key
        self.oauth_key = settings["google_oauth"]["key"]

        # Setup the Tornado Application
        cookie_secret = base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)
        settings["debug"]= True
        settings["static_path"]= "static"
        settings["cookie_secret"]= cookie_secret
        settings["login_url"]= "/login"


        if options['develop']:
            tornado.autoreload.watch("design/application.html")
            tornado.autoreload.watch("design/applications.html")
            tornado.autoreload.watch("design/barcode_vs_expected.html")
            tornado.autoreload.watch("design/base.html")
            tornado.autoreload.watch("design/bioinfo_tab.html")
            tornado.autoreload.watch("design/bioinfo_tab/run_lane_sample_view.html")
            tornado.autoreload.watch("design/bioinfo_tab/sample_run_lane_view.html")
            tornado.autoreload.watch("design/clusters_per_lane.html")
            tornado.autoreload.watch("design/cronjobs.html")
            tornado.autoreload.watch("design/deliveries.html")
            tornado.autoreload.watch("design/error_page.html")
            tornado.autoreload.watch("design/flowcell.html")
            tornado.autoreload.watch("design/flowcell_error.html")
            tornado.autoreload.watch("design/flowcell_samples.html")
            tornado.autoreload.watch("design/flowcells.html")
            tornado.autoreload.watch("design/index.html")
            tornado.autoreload.watch("design/instrument_logs.html")
            tornado.autoreload.watch("design/link_tab.html")
            tornado.autoreload.watch("design/nas_quotas.html")
            tornado.autoreload.watch("design/phix_err_rate.html")
            tornado.autoreload.watch("design/production.html")
            tornado.autoreload.watch("design/proj_meta_compare.html")
            tornado.autoreload.watch("design/project_samples.html")
            tornado.autoreload.watch("design/project_summary.html")
            tornado.autoreload.watch("design/projects.html")
            tornado.autoreload.watch("design/q30.html")
            tornado.autoreload.watch("design/reads_per_lane.html")
            tornado.autoreload.watch("design/reads_total.html")
            tornado.autoreload.watch("design/reads_vs_qv.html")
            tornado.autoreload.watch("design/rec_ctrl_view.html")
            tornado.autoreload.watch("design/running_notes_help.html")
            tornado.autoreload.watch("design/running_notes_tab.html")
            tornado.autoreload.watch("design/samples_per_lane.html")
            tornado.autoreload.watch("design/sequencing_stats.html")
            tornado.autoreload.watch("design/suggestion_box.html")
            tornado.autoreload.watch("design/unauthorized.html")
            tornado.autoreload.watch("design/uppmax_quotas.html")
            tornado.autoreload.watch("design/workset_placement.html")
            tornado.autoreload.watch("design/workset_samples.html")
            tornado.autoreload.watch("design/worksets.html")
            tornado.autoreload.watch("design/yield_plot.html")

        tornado.web.Application.__init__(self, handlers, **settings)


if __name__ == '__main__':
    # Tornado built-in command line parsing. Auto configures logging
    define('testing_mode', default=False, help=("WARNING, this option disables "
                                                "all security measures, use only "
                                                "for testing purposes"))
    define('develop', default=False, help=("Define develop mode to look for changes "
                                           "in files and automatically reloading them"))
    # After parsing the command line, the command line flags are stored in tornado.options
    tornado.options.parse_command_line()

    # Load configuration file
    with open("settings.yaml") as settings_file:
        server_settings = yaml.load(settings_file)

    server_settings["Testing mode"] = options['testing_mode']

    # Instantiate Application
    application = Application(server_settings)

    # Load ssl certificate and key files
    ssl_cert = server_settings.get("ssl_cert", None)
    ssl_key = server_settings.get("ssl_key", None)

    if ssl_cert and ssl_key:
        ssl_options = {"certfile": ssl_cert,
                       "keyfile": ssl_key}
    else:
        ssl_options = None

    # Start HTTP Server
    http_server = tornado.httpserver.HTTPServer(application,
                                                ssl_options = ssl_options)

    http_server.listen(server_settings.get("port", 8888))

    # Get a handle to the instance of IOLoop
    ioloop = tornado.ioloop.IOLoop.instance()

    # Start the IOLoop
    ioloop.start()
