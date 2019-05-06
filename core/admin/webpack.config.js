var path = require("path");
var webpack = require("webpack");
var css = require("mini-css-extract-plugin");

module.exports = {
    mode: "development",
    entry: {
        app: "./assets/app.js",
        vendor: "./assets/vendor.js"
    },
    output: {
        path: path.resolve(__dirname, "mailu/ui/static/"),
        filename: "[name].js",
        publicPath: "/static"
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                use: {
                    loader: "babel-loader",
                    options: {
                        presets: ['@babel/preset-env']
                    }
                }
            },
            {
                test: /\.scss$/,
                use: [css.loader, 'css-loader', 'sass-loader']
            },
            {
                test: /\.less$/,
                use: [css.loader, 'css-loader', 'less-loader']
            },
            {
                test: /\.css$/,
                use: [css.loader, 'css-loader']
            },
            {
                test: /\.woff($|\?)|\.woff2($|\?)|\.ttf($|\?)|\.eot($|\?)|\.svg($|\?)/,
                use: ['url-loader']
            }
        ]
    },
    plugins: [
	      new css({
	          filename: "[name].css",
	          chunkFilename: "[id].css"
	      }),
        new webpack.ProvidePlugin({
            $: "jquery",
            jQuery: "jquery"
        })
    ]
}

